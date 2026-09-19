"""
tests/unit/test_contract_review_agent.py
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from agents import contract_review_agent


VALID_LLM_RESPONSE = json.dumps({
    "is_valid_contract": True,
    "intake_notes": "",
    "contract_metadata": {
        "parties": ["Acme Corp", "WidgetCo Ltd"],
        "effective_date": "2025-01-01",
        "expiry_date": "2025-12-31",
        "term": "12 months",
        "contract_type": "Service Agreement",
        "governing_law": "Delaware",
        "jurisdiction": None,
    },
})

INVALID_DOCUMENT_RESPONSE = json.dumps({
    "is_valid_contract": False,
    "intake_notes": "This is a marketing brochure, not a contract.",
    "contract_metadata": {},
})


class TestContractReviewAgent:
    @pytest.mark.asyncio
    async def test_valid_contract_extracted(self, minimal_state, mock_ollama):
        mock_ollama.return_value = VALID_LLM_RESPONSE

        result = await contract_review_agent.run(minimal_state)

        assert result["is_valid_contract"] is True
        assert result["contract_metadata"]["contract_type"] == "Service Agreement"
        assert "Acme Corp" in result["contract_metadata"]["parties"]
        assert result["intake_notes"] == ""

    @pytest.mark.asyncio
    async def test_invalid_document_flagged(self, minimal_state, mock_ollama):
        mock_ollama.return_value = INVALID_DOCUMENT_RESPONSE

        result = await contract_review_agent.run(minimal_state)

        assert result["is_valid_contract"] is False
        assert "brochure" in result["intake_notes"]

    @pytest.mark.asyncio
    async def test_empty_raw_text_returns_invalid(self):
        """Empty text short-circuits before calling Ollama."""
        state = {"contract_id": "test", "raw_text": "", "errors": [], "completed_steps": []}
        result = await contract_review_agent.run(state)

        assert result["is_valid_contract"] is False
        assert "No text" in result["intake_notes"]

    @pytest.mark.asyncio
    async def test_llm_failure_fails_closed(self, minimal_state, mock_ollama):
        """If Ollama errors, agent rejects the document (fail-closed) rather than
        letting an unvalidated document flow through the pipeline."""
        mock_ollama.side_effect = RuntimeError("Ollama is down")

        result = await contract_review_agent.run(minimal_state)

        # Should NOT raise; should fail closed
        assert result["is_valid_contract"] is False
        assert "failed" in result["intake_notes"].lower()
        assert result["contract_metadata"]["parties"] == []

    @pytest.mark.asyncio
    async def test_result_contains_required_keys(self, minimal_state, mock_ollama):
        mock_ollama.return_value = VALID_LLM_RESPONSE

        result = await contract_review_agent.run(minimal_state)

        assert "contract_metadata" in result
        assert "is_valid_contract" in result
        assert "intake_notes" in result

    @pytest.mark.asyncio
    async def test_metadata_missing_fields_default_to_none(self, minimal_state, mock_ollama):
        """LLM returns partial metadata — missing fields should default, not crash."""
        mock_ollama.return_value = json.dumps({
            "is_valid_contract": True,
            "intake_notes": "",
            "contract_metadata": {"parties": ["Acme"]},  # most fields missing
        })

        result = await contract_review_agent.run(minimal_state)

        assert result["contract_metadata"]["parties"] == ["Acme"]
        assert result["contract_metadata"]["effective_date"] is None
