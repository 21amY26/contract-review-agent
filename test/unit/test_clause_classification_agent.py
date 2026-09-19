"""
tests/unit/test_clause_classification_agent.py
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from agents import clause_classification_agent


def _clause_response(clause_id: str, category: str, risk_flag: bool = False) -> str:
    return json.dumps([{
        "clause_id": clause_id,
        "text": "some clause text",
        "category": category,
        "confidence": 0.9,
        "risk_flag": risk_flag,
    }])


class TestClauseClassificationAgent:
    @pytest.mark.asyncio
    async def test_classifies_all_chunks(self, minimal_state, mock_ollama):
        """Each chunk should produce one classified clause."""
        # Return a different category per call to make assertions meaningful.
        categories = ["other", "payment", "other", "termination", "governing_law"]
        mock_ollama.side_effect = [
            _clause_response(f"clause_{i:03d}", cat)
            for i, cat in enumerate(categories)
        ]

        result = await clause_classification_agent.run(minimal_state)

        clauses = result["classified_clauses"]
        assert len(clauses) == 5
        assert clauses[1]["category"] == "payment"
        assert clauses[3]["category"] == "termination"

    @pytest.mark.asyncio
    async def test_no_chunks_uses_raw_text(self, minimal_state, mock_ollama):
        """If chunks is empty, falls back to raw_text as a single chunk."""
        state = {**minimal_state, "chunks": []}
        mock_ollama.return_value = _clause_response("clause_000", "other")

        result = await clause_classification_agent.run(state)

        assert len(result["classified_clauses"]) == 1

    @pytest.mark.asyncio
    async def test_empty_state_returns_empty_list(self):
        """No chunks and no raw_text → empty list, no crash."""
        state = {"contract_id": "test", "raw_text": "", "chunks": [], "errors": [], "completed_steps": []}

        result = await clause_classification_agent.run(state)

        assert result["classified_clauses"] == []

    @pytest.mark.asyncio
    async def test_partial_llm_failure_skips_bad_chunk(self, minimal_state, mock_ollama):
        """If one chunk's LLM call fails, the others still succeed."""
        responses = [
            _clause_response("clause_000", "other"),
            RuntimeError("LLM timeout"),   # second chunk fails
            _clause_response("clause_002", "payment"),
            _clause_response("clause_003", "termination"),
            _clause_response("clause_004", "governing_law"),
        ]
        mock_ollama.side_effect = responses

        result = await clause_classification_agent.run(minimal_state)

        # 4 of 5 should succeed; the failed one is skipped (returns None → filtered)
        clauses = result["classified_clauses"]
        assert len(clauses) == 4

    @pytest.mark.asyncio
    async def test_risk_flag_preserved(self, minimal_state, mock_ollama):
        """risk_flag=True from LLM should appear in output."""
        mock_ollama.side_effect = [
            _clause_response(f"clause_{i:03d}", "other", risk_flag=(i == 2))
            for i in range(5)
        ]

        result = await clause_classification_agent.run(minimal_state)

        risk_flagged = [c for c in result["classified_clauses"] if c["risk_flag"]]
        assert len(risk_flagged) == 1
        assert risk_flagged[0]["clause_id"] == "clause_002"

    @pytest.mark.asyncio
    async def test_multiple_clauses_from_one_chunk(self, minimal_state, mock_ollama):
        """A chunk whose LLM response is a multi-element array yields multiple
        classified clauses with unique ids."""
        state = {**minimal_state, "chunks": ["1. Payment ... 2. Termination ..."]}
        mock_ollama.return_value = json.dumps([
            {"clause_id": "a", "text": "payment text", "category": "payment",
             "confidence": 0.9, "risk_flag": False},
            {"clause_id": "b", "text": "termination text", "category": "termination",
             "confidence": 0.8, "risk_flag": True},
        ])

        result = await clause_classification_agent.run(state)

        clauses = result["classified_clauses"]
        assert len(clauses) == 2
        assert {c["category"] for c in clauses} == {"payment", "termination"}

    @pytest.mark.asyncio
    async def test_structural_metadata_preserved(self, mock_ollama):
        """section_id/heading from dict chunks flow into the classified clause
        when the model doesn't supply its own."""
        state = {
            "contract_id": "test", "raw_text": "x", "errors": [], "completed_steps": [],
            "chunks": [
                {"text": "Provider shall indemnify Client.", "section_id": "8.2",
                 "heading": "Indemnification", "chunk_index": 0},
            ],
        }
        mock_ollama.return_value = json.dumps([
            {"clause_id": "c0", "text": "Provider shall indemnify Client.",
             "category": "indemnification", "confidence": 0.95, "risk_flag": True},
        ])

        result = await clause_classification_agent.run(state)

        clause = result["classified_clauses"][0]
        assert clause["section_id"] == "8.2"
        assert clause["heading"] == "Indemnification"

    @pytest.mark.asyncio
    async def test_output_key_is_classified_clauses(self, minimal_state, mock_ollama):
        mock_ollama.return_value = _clause_response("clause_000", "other")
        # Only one chunk for simplicity
        state = {**minimal_state, "chunks": [minimal_state["chunks"][0]]}

        result = await clause_classification_agent.run(state)

        assert "classified_clauses" in result
        assert isinstance(result["classified_clauses"], list)
