"""
agents/contract_review_agent.py

Contract intake / validation / metadata extraction.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.llm_router import chat_json
from agents.schemas import ContractReviewOutput
from src.metadata.classifier import classify_document_type

logger = logging.getLogger(__name__)

_EXCERPT_CHARS = 6000

_SYSTEM_PROMPT = """You are an intake reviewer for a contract-analysis system.

Given an excerpt of an uploaded document, decide:

1. Is this actually a contract / legal agreement
   (NDA, MSA, lease, SOW, employment agreement,
   vendor/distributor agreement, terms of service, etc.)?

2. If it is a contract, extract:
   - parties
   - effective_date
   - expiry_date
   - term
   - contract_type
   - governing_law
   - jurisdiction

Return ONLY valid JSON matching the requested schema.
"""


async def run(state: dict[str, Any]) -> dict[str, Any]:
    raw_text = state.get("raw_text") or ""

    if not raw_text.strip():
        return {
            "is_valid_contract": False,
            "intake_notes": "No text could be extracted from the uploaded document.",
            "contract_metadata": {
                "parties": [],
                "effective_date": None,
                "expiry_date": None,
                "term": None,
                "contract_type": None,
                "governing_law": None,
                "jurisdiction": None,
            },
        }

    excerpt = raw_text[:_EXCERPT_CHARS]

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Document excerpt:\n\n{excerpt}",
        },
    ]

    try:
        parsed = await chat_json(messages)
        result = ContractReviewOutput.model_validate(parsed)

    except Exception as exc:
        logger.warning("Contract review failed: %s", exc)

        # Fail closed: if we cannot validate the document (LLM outage, malformed
        # response, etc.), reject it rather than letting an unvalidated document
        # flow through the entire downstream pipeline.
        return {
            "is_valid_contract": False,
            "intake_notes": f"Contract validation failed: {exc}",
            "contract_metadata": {
                "parties": [],
                "effective_date": None,
                "expiry_date": None,
                "term": None,
                "contract_type": None,
                "governing_law": None,
                "jurisdiction": None,
            },
        }

    metadata = result.contract_metadata.model_copy()

    filename = (state.get("file_metadata") or {}).get("filename")

    if (
        filename
        and (
            metadata.contract_type is None
            or metadata.contract_type.lower() == "unknown"
        )
    ):
        heuristic = classify_document_type(Path(filename))

        if heuristic != "Unknown":
            metadata.contract_type = heuristic

    return {
        "is_valid_contract": result.is_valid_contract,
        "intake_notes": result.intake_notes,
        "contract_metadata": metadata.model_dump(),
    }
