# agents/orchestration/graph.py

LangGraph workflow definition for the Contract Review & Compliance Risk Management system's **Orchestration Layer** (see the architecture diagram).

## Pipeline

```
START
  |
  v
contract_review_agent            <- intake / validation / metadata extraction
  |
  v
[conditional: is_valid_contract?]
  |--- False --> early_exit --> END
  |
  v (True / unknown-due-to-error)
clause_classification_agent      <- classifies clauses BEFORE downstream agents
  |                                  use them (per project decision)
  v
document_understanding_node      <- COMBINED node: internally calls both
  |                                  document_understanding_agent.run() and
  |                                  knowledge_retrieval_agent.run() concurrently.
  |                                  This is a single LangGraph node, not two,
  |                                  per the diagram drawing them as one box.
  |
  +------------------+
  v                  v
compliance_agent   risk_agent     <- run CONCURRENTLY (parallel fan-out).
  |                  |               LangGraph automatically runs these
  +------------------+               together since both only depend on
  v                                  document_understanding_node, and
recommendation_agent                 automatically waits for BOTH (fan-in)
  |                                  before recommendation_agent runs.
  v
legal_explanation_agent
  |
  v
finalize  --> END
```

**Note:** "Final Report Generator" is intentionally **not** a node in this graph. In the architecture diagram it sits visually outside the "Orchestration Layer" box, and PDF generation (`reports/pdf_generator.py`) is a separate concern from the analysis pipeline — the FastAPI backend should call it **after** this graph finishes, using the final state this graph returns.

## Required agent files

You create/rename these under `agents/` before this module will import successfully:

| File | Status |
|---|---|
| `contract_review_agent.py` | new |
| `clause_classification_agent.py` | existing |
| `document_understanding_agent.py` | existing |
| `knowledge_retrieval_agent.py` | new |
| `compliance_agent.py` | renamed from `compliance_verification_agent.py` |
| `risk_agent.py` | renamed from `risk_assessment_agent.py` |
| `recommendation_agent.py` | existing |
| `legal_explanation_agent.py` | existing |

`knowledge_retrieval_agent.py` is called *inside* the combined `document_understanding` node — it is not its own graph node, since the diagram draws "Document Understanding Agent + Knowledge Retrieval Agent" as a single box.

## Expected agent interface

Every file above must expose:

```python
async def run(state: ContractReviewState) -> dict:
    ...
```

- Receives the full current graph state (read-only in practice).
- Returns a **partial update dict** containing only the keys this agent is responsible for setting (LangGraph merges it into the full state).
- Should raise on unrecoverable failure — `graph.py` catches it, records it in `state["errors"]`, and lets the pipeline continue with degraded data (see Error handling policy below).

### Suggested return shapes (the agent implementation owns the real shape)

- `contract_metadata`: `{"parties": [...], "effective_date": ..., "term": ..., "contract_type": ..., "governing_law": ...}`
- `classified_clauses`: `[{"clause_id": str, "text": str, "category": str, "confidence": float}, ...]`
- `retrieved_context`: `[{"source": str, "content": str, "score": float}, ...]`
- `compliance_results`: `{"violations": [...], "compliant": bool, ...}`
- `risk_results`: `{"overall_risk_score": float, "risk_items": [...]}`

## Error handling policy

If any agent raises, `graph.py`:
1. Catches it.
2. Appends a structured entry to `state["errors"]`.
3. Records a `"<agent>_failed"` entry in `completed_steps`.
4. Lets the pipeline **continue** with whatever partial data is available.

The pipeline never hard-crashes because one agent failed. The one exception is `contract_review_agent`'s own explicit business decision (`is_valid_contract == False`) — that's a deliberate early exit, not an error.

If `contract_review_agent` itself *crashes* (rather than explicitly returning `is_valid_contract=False`), the pipeline treats that as "unknown" and continues — only an explicit `False` triggers early exit, consistent with the degraded-continuation policy.

## Concurrency model

All nodes are async. The compliance/risk fan-out and the internal document-understanding + knowledge-retrieval calls use `asyncio.gather` so concurrent Groq/Gemini/Ollama API calls actually overlap in wall-clock time.

## State schema (`ContractReviewState`)

`errors` and `completed_steps` use the `operator.add` reducer because `compliance_agent` and `risk_agent` write to them **concurrently** in the same superstep. Without a reducer, LangGraph raises `INVALID_CONCURRENT_GRAPH_UPDATE` on parallel writes to the same key.

Use `create_initial_state(contract_id, raw_text, chunks=None, file_metadata=None)` to construct a valid initial state without having to remember every key.

## Persistence

Uses LangGraph's `AsyncSqliteSaver` checkpointer so runs are resumable and inspectable mid-flow (e.g. for a progress dashboard or human-in-the-loop pause).

### Recommended usage (FastAPI)

Open the graph **once** at app startup via a lifespan handler and reuse the compiled graph across all requests. Opening a fresh sqlite connection per request is wasteful and won't scale under concurrent load.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from agents.orchestration.graph import build_contract_review_graph, create_initial_state

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with build_contract_review_graph() as graph:
        app.state.contract_review_graph = graph
        yield

app = FastAPI(lifespan=lifespan)

@app.post("/contracts/{contract_id}/analyze")
async def analyze(contract_id: str, raw_text: str):
    initial_state = create_initial_state(contract_id, raw_text)
    config = {"configurable": {"thread_id": contract_id}}
    result = await app.state.contract_review_graph.ainvoke(initial_state, config=config)
    return result
```

### One-off usage (scripts/tests)

```python
from agents.orchestration.graph import run_contract_review, create_initial_state

state = create_initial_state(contract_id="demo-001", raw_text="...")
result = await run_contract_review(state, thread_id="demo-001")
```

`run_contract_review` opens a sqlite connection, runs the graph once, and closes it. Fine for low-traffic/dev use; for a FastAPI backend handling concurrent requests, use `build_contract_review_graph()` once at startup instead.

## Verified behavior

Before delivery this graph was run end-to-end with mock agents to confirm:

1. **Valid contract path** — full chain runs; `compliance_agent` and `risk_agent` actually execute concurrently, then both are waited on before `recommendation_agent` runs.
2. **Agent failure mid-pipeline** — a forced exception in `risk_agent` was caught and logged into `state["errors"]`; the pipeline kept going (`recommendation_agent` and `legal_explanation_agent` still ran on the remaining data); final status came back `completed_with_errors`.
3. **Invalid contract path** — empty input triggers the early-exit branch right after `contract_review_agent`, skipping all downstream LLM calls; status `failed`.

## Judgment calls made (not explicitly specified — flagged for review)

- Added an `early_exit` node and a `finalize` node. Neither was in the original diagram, but they're natural complements to the conditional-exit and checkpointing decisions made for this pipeline.
- `early_exit` only fires on an *explicit* `is_valid_contract=False`; a crash in `contract_review_agent` is treated as "unknown" and the pipeline continues, per the degraded-continuation error policy.
