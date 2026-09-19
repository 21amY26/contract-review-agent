"""
agents/clause_classification_agent.py

Classifies each chunk in `state["chunks"]` into a legal clause category
(indemnification, payment, termination, IP, …) and flags risky clauses
for downstream agents to prioritise.

Returns partial state keys:
    classified_clauses   list[ClassifiedClause dict]
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from agents import llm_router
from agents.schemas import ClassifiedClause, ClauseClassificationOutput

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a contract clause classifier. For each clause provided, return a JSON array.
Each element must follow this schema exactly:
{
  "clause_id": "<str>",
  "text": "<verbatim clause text>",
  "category": "<one of: indemnification | payment | termination | liability_cap | ip_ownership | confidentiality | data_privacy | dispute_resolution | auto_renewal | warranty | force_majeure | governing_law | other>",
  "confidence": <0.0–1.0>,
  "risk_flag": <true | false>
}

Set risk_flag=true for clauses that are one-sided, unusually broad, missing standard protections, or create material exposure.
Respond ONLY with the JSON array. No prose, no markdown fences.
"""


def _chunk_fields(chunk: Any) -> tuple[str, str | None, str | None]:
    """Normalize a chunk (dict from the splitter, or a bare string) to
    (text, section_id, heading)."""
    if isinstance(chunk, dict):
        return chunk.get("text", ""), chunk.get("section_id"), chunk.get("heading")
    return str(chunk), None, None


async def _classify_chunk(chunk: Any, chunk_id: str, contract_id: str) -> list[ClassifiedClause]:
    """Send a single chunk for classification. Returns a list of classified
    clauses (a chunk may contain more than one). Empty list on failure."""
    text, section_id, heading = _chunk_fields(chunk)
    if not text.strip():
        return []

    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"CLAUSE ID: {chunk_id}\n\n"
                f"CLAUSE TEXT:\n{text[:2_000]}"   # safety truncation
            ),
        },
    ]
    try:
        parsed = await llm_router.chat_json(messages)
        # The model may return a list (multiple clauses) or a single object.
        items = parsed if isinstance(parsed, list) else [parsed]
        clauses: list[ClassifiedClause] = []
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            # Give each clause from the same chunk a unique, stable id.
            item.setdefault("clause_id", chunk_id if i == 0 else f"{chunk_id}_{i}")
            item.setdefault("text", text[:500])
            # Preserve structural context from the chunker unless the model
            # supplied its own.
            item.setdefault("section_id", section_id)
            item.setdefault("heading", heading)
            clauses.append(ClassifiedClause(**item))
        return clauses
    except Exception as exc:
        logger.warning("[%s] clause classification failed for %s: %s", contract_id, chunk_id, exc)
        return []


async def run(state: dict[str, Any]) -> dict[str, Any]:
    contract_id: str = state.get("contract_id", "unknown")
    chunks: list[Any] = state.get("chunks", [])

    # Fallback: if the pipeline was called without pre-chunked text, treat the
    # whole raw_text as one chunk so the agent still produces *something*.
    if not chunks:
        raw = state.get("raw_text", "")
        if raw.strip():
            chunks = [raw]

    if not chunks:
        logger.warning("[%s] clause_classification_agent: no chunks to classify", contract_id)
        return {"classified_clauses": []}

    # Classify all chunks concurrently (Ollama handles one request at a time
    # locally, but the gather keeps code ready for a real API with parallelism).
    tasks = [
        _classify_chunk(chunk, f"clause_{i:03d}", contract_id)
        for i, chunk in enumerate(chunks)
    ]
    results = await asyncio.gather(*tasks)

    # Each task returns a list[ClassifiedClause]; flatten them.
    classified = [c.model_dump() for chunk_clauses in results for c in chunk_clauses]

    logger.info(
        "[%s] clause_classification_agent → %d/%d clauses classified, %d flagged",
        contract_id,
        len(classified),
        len(chunks),
        sum(1 for c in classified if c.get("risk_flag")),
    )

    return {"classified_clauses": classified}