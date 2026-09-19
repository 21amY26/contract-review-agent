from __future__ import annotations

import asyncio
import logging
import operator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agents import contract_review_agent
from agents import clause_classification_agent
from agents import document_understanding_agent
from agents import compliance_agent
from agents import risk_agent
from agents import recommendation_agent
from agents import legal_explanation_agent

logger = logging.getLogger("contract_review.orchestration")

DEFAULT_CHECKPOINT_PATH = "./agents/orchestration/contract_review_checkpoints.db"


class ContractReviewState(TypedDict, total=False):
    contract_id: str
    raw_text: str
    # Each chunk is a dict: {"text", "section_id", "heading", "chunk_index"}.
    # Plain strings are also tolerated by clause_classification_agent for
    # backward compatibility.
    chunks: List[Dict[str, Any]]
    file_metadata: Dict[str, Any]

    contract_metadata: Optional[Dict[str, Any]]
    is_valid_contract: Optional[bool]
    intake_notes: Optional[str]

    classified_clauses: Optional[List[Dict[str, Any]]]

    document_summary: Optional[str]
    key_terms: Optional[Dict[str, Any]]
    retrieved_context: Optional[List[Dict[str, Any]]]

    compliance_results: Optional[Dict[str, Any]]

    risk_results: Optional[Dict[str, Any]]

    recommendations: Optional[List[Dict[str, Any]]]

    legal_explanations: Optional[List[Dict[str, Any]]]

    errors: Annotated[List[Dict[str, Any]], operator.add]
    completed_steps: Annotated[List[str], operator.add]

    status: Literal["in_progress", "completed", "completed_with_errors", "rejected", "failed"]
    started_at: Optional[str]
    completed_at: Optional[str]


def create_initial_state(
    contract_id: str,
    raw_text: str,
    chunks: Optional[List[str]] = None,
    file_metadata: Optional[Dict[str, Any]] = None,
) -> ContractReviewState:
    return ContractReviewState(
        contract_id=contract_id,
        raw_text=raw_text,
        chunks=chunks or [],
        file_metadata=file_metadata or {},
        contract_metadata=None,
        is_valid_contract=None,
        intake_notes=None,
        classified_clauses=None,
        document_summary=None,
        key_terms=None,
        retrieved_context=None,
        compliance_results=None,
        risk_results=None,
        recommendations=None,
        legal_explanations=None,
        errors=[],
        completed_steps=[],
        status="in_progress",
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=None,
    )


async def _safe_call(agent_name: str, agent_run, state: ContractReviewState) -> Dict[str, Any]:
    try:
        result = await agent_run(state)
        result = dict(result) if result else {}
        result["completed_steps"] = result.get("completed_steps", []) + [agent_name]
        return result
    except Exception as exc:
        logger.exception("Agent '%s' failed for contract_id=%s", agent_name, state.get("contract_id"))
        return {
            "errors": [
                {
                    "agent": agent_name,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "completed_steps": [f"{agent_name}_failed"],
        }


async def contract_review_node(state: ContractReviewState) -> Dict[str, Any]:
    return await _safe_call("contract_review_agent", contract_review_agent.run, state)


async def early_exit_node(state: ContractReviewState) -> Dict[str, Any]:
    # Reached when contract_review_agent determines the document is not a valid
    # contract. This is a deliberate rejection, NOT a pipeline crash — hence the
    # distinct "rejected" status so the UI can message it clearly.
    return {
        "status": "rejected",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "completed_steps": ["early_exit"],
    }


async def clause_classification_node(state: ContractReviewState) -> Dict[str, Any]:
    return await _safe_call("clause_classification_agent", clause_classification_agent.run, state)


async def document_understanding_node(state: ContractReviewState) -> Dict[str, Any]:
    # RAG retrieval is now performed inside document_understanding_agent itself
    # (it calls src.retrieval.search_contracts and returns retrieved_context),
    # so there is no separate knowledge_retrieval_agent to fan out to here.
    return await _safe_call(
        "document_understanding_agent", document_understanding_agent.run, state
    )


async def compliance_node(state: ContractReviewState) -> Dict[str, Any]:
    return await _safe_call("compliance_agent", compliance_agent.run, state)


async def risk_node(state: ContractReviewState) -> Dict[str, Any]:
    return await _safe_call("risk_agent", risk_agent.run, state)


async def recommendation_node(state: ContractReviewState) -> Dict[str, Any]:
    return await _safe_call("recommendation_agent", recommendation_agent.run, state)


async def legal_explanation_node(state: ContractReviewState) -> Dict[str, Any]:
    return await _safe_call("legal_explanation_agent", legal_explanation_agent.run, state)


async def finalize_node(state: ContractReviewState) -> Dict[str, Any]:
    had_errors = bool(state.get("errors"))
    return {
        "status": "completed_with_errors" if had_errors else "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "completed_steps": ["finalize"],
    }


def route_after_contract_review(state: ContractReviewState) -> str:
    if state.get("is_valid_contract") is False:
        return "stop"
    return "continue"


def _build_graph_definition() -> StateGraph:
    graph = StateGraph(ContractReviewState)

    graph.add_node("contract_review_agent", contract_review_node)
    graph.add_node("early_exit", early_exit_node)
    graph.add_node("clause_classification_agent", clause_classification_node)
    graph.add_node("document_understanding", document_understanding_node)
    graph.add_node("compliance_agent", compliance_node)
    graph.add_node("risk_agent", risk_node)
    graph.add_node("recommendation_agent", recommendation_node)
    graph.add_node("legal_explanation_agent", legal_explanation_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "contract_review_agent")

    graph.add_conditional_edges(
        "contract_review_agent",
        route_after_contract_review,
        {"continue": "clause_classification_agent", "stop": "early_exit"},
    )
    graph.add_edge("early_exit", END)

    graph.add_edge("clause_classification_agent", "document_understanding")

    graph.add_edge("document_understanding", "compliance_agent")
    graph.add_edge("document_understanding", "risk_agent")
    graph.add_edge("compliance_agent", "recommendation_agent")
    graph.add_edge("risk_agent", "recommendation_agent")

    graph.add_edge("recommendation_agent", "legal_explanation_agent")
    graph.add_edge("legal_explanation_agent", "finalize")
    graph.add_edge("finalize", END)

    return graph


@asynccontextmanager
async def build_contract_review_graph(checkpoint_path: str = DEFAULT_CHECKPOINT_PATH):
    async with AsyncSqliteSaver.from_conn_string(checkpoint_path) as checkpointer:
        compiled = _build_graph_definition().compile(checkpointer=checkpointer)
        yield compiled


async def run_contract_review(
    initial_state: ContractReviewState,
    thread_id: str,
    checkpoint_path: str = DEFAULT_CHECKPOINT_PATH,
) -> ContractReviewState:
    async with build_contract_review_graph(checkpoint_path) as compiled_graph:
        config = {"configurable": {"thread_id": thread_id}}
        return await compiled_graph.ainvoke(initial_state, config=config)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def _demo():
        state = create_initial_state(
            contract_id="demo-contract-001",
            raw_text="This is a sample contract body for local testing...",
        )
        result = await run_contract_review(state, thread_id="demo-contract-001")
        print("Final status:", result.get("status"))
        print("Completed steps:", result.get("completed_steps"))
        print("Errors:", result.get("errors"))

    asyncio.run(_demo())
