"""
agents/document_understanding_agent.py

Produces a plain-English summary of the contract and extracts key commercial
terms (payment amounts, notice periods, renewal windows, etc.).

Returns partial state keys:
    document_summary   str
    key_terms          dict
"""
from __future__ import annotations

import json
import logging
from typing import Any

from agents import llm_router
from agents.schemas import DocumentUnderstandingOutput
from src.retrieval.retriever import search_contracts

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a contract analyst. Read the contract text and:
1. Write a concise executive summary (3–5 sentences) of what this contract is about and what each party's core obligations are.
2. Extract key commercial terms as a flat JSON object.

Respond ONLY with a JSON object. No prose, no markdown fences.

Schema:
{
  "document_summary": "<3–5 sentence summary>",
  "key_terms": {
    "payment_amount": "<string or null>",
    "payment_schedule": "<string or null>",
    "notice_period": "<string or null>",
    "auto_renewal": "<true|false|null>",
    "renewal_notice_window": "<string or null>",
    "liability_cap": "<string or null>",
    "ip_ownership": "<string or null>",
    "non_compete": "<string or null>",
    "termination_for_convenience": "<true|false|null>"
  }
}
"""


async def run(state: dict[str, Any]) -> dict[str, Any]:
    contract_id: str = state.get("contract_id", "unknown")
    raw_text: str = state.get("raw_text", "")

    # Prefer the full text; truncate generously for LLM context.
    excerpt = raw_text[:6_000]

    if not excerpt.strip():
        return {"document_summary": "", "key_terms": {}, "retrieved_context": []}

    # RAG: pull similar reference contracts from the KB for framing/context.
    # Degrades to [] gracefully when the KB is unbuilt (see retriever._search).
    retrieved_context: list[dict[str, Any]] = []
    try:
        retrieved_context = search_contracts(excerpt[:1_000], n_results=3)
    except Exception as exc:
        logger.warning("[%s] contract retrieval failed: %s", contract_id, exc)

    context_block = "\n\n".join(
        f"[{r['metadata'].get('citation', r['metadata'].get('source', 'reference'))}]\n{r['text']}"
        for r in retrieved_context
    )

    user_content = f"CONTRACT TEXT:\n\n{excerpt}"
    if context_block:
        user_content += (
            "\n\nFor reference only — excerpts from similar contracts in our "
            f"knowledge base (do not treat as part of this contract):\n{context_block}"
        )

    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_content},
    ]

    try:
        parsed = await llm_router.chat_json(messages)
    except Exception as exc:
        logger.error("[%s] document_understanding_agent error: %s", contract_id, exc)
        return {"document_summary": "", "key_terms": {}, "retrieved_context": retrieved_context}

    output = DocumentUnderstandingOutput(
        document_summary=str(parsed.get("document_summary", "")),
        key_terms=parsed.get("key_terms") or {},
    )

    logger.info(
        "[%s] document_understanding_agent → summary=%d chars, %d key terms",
        contract_id,
        len(output.document_summary),
        len(output.key_terms),
    )

    return {
        "document_summary": output.document_summary,
        "key_terms": output.key_terms,
        "retrieved_context": retrieved_context,
    }