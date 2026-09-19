# Week-1 Knowledge Base

This folder contains seed knowledge and persistent ChromaDB storage for the Contract Review & Compliance Assistant.

## Collections

- `contracts`: parsed contract chunks from PDF, DOCX, and DOCM files.
- `compliance`: markdown/text compliance sources and internal policies.
- `risk`: JSON risk rules, one rule per Chroma document.

## Ingestion Commands

```bash
python -m src.ingestion.ingest_contracts kb/contracts
python -m src.ingestion.ingest_compliance kb/policies
python -m src.ingestion.ingest_risks kb/risks/risk_rules.json
```

## Rebuild Command

```bash
./build_kb.sh
```

This recreates `kb/chroma/` from the tracked contract, policy, and risk sources.

## Retrieval Commands

```bash
python -m src.retrieval.retriever contracts "termination for convenience notice period"
python -m src.retrieval.retriever compliance "GDPR processor security obligations Article 28"
python -m src.retrieval.retriever risk "unlimited liability indemnity exposure"
```

## Python Usage

```python
from src.retrieval.retriever import search_contracts, search_compliance, search_risks

contract_hits = search_contracts("limitation of liability", n_results=5)
compliance_hits = search_compliance("GDPR Article 32 encryption", n_results=5)
risk_hits = search_risks("uncapped indemnity", n_results=5)
```

Every result includes `text`, `metadata`, and `score`. Citation data is exposed through `metadata["citation"]`.
