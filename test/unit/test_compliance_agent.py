"""
tests/unit/test_compliance_agent.py
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from agents import compliance_agent


def _mock_retrieval(*_args, **_kwargs):
    """Fake search_compliance result — avoids needing a real ChromaDB."""
    return [
        {
            "text": "Data processing agreements must define purpose, security obligations, "
                    "subprocessor controls, and deletion timelines.",
            "metadata": {"citation": "GDPR Article 28"},
            "score": 0.82,
        }
    ]


def _llm_response(violations=None, missing=None, compliant=True):
    return json.dumps({
        "compliant": compliant,
        "violations": violations or [],
        "missing_requirements": missing or [],
    })


@pytest.fixture(autouse=True)
def _patch_retrieval():
    """Every test in this file gets a mocked search_compliance automatically."""
    with patch("agents.compliance_agent.search_compliance", side_effect=_mock_retrieval):
        yield


class TestComplianceAgent:
    @pytest.mark.asyncio
    async def test_no_relevant_clauses_returns_compliant(self, minimal_state, mock_ollama):
        """A contract with no policy-relevant clause categories should skip the LLM entirely."""
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_000", "text": "...", "category": "payment", "confidence": 0.9, "risk_flag": False},
            ],
        }

        result = await compliance_agent.run(state)

        assert result["compliance_results"]["compliant"] is True
        assert result["compliance_results"]["violations"] == []
        mock_ollama.assert_not_called()

    @pytest.mark.asyncio
    async def test_violation_found_includes_likelihood_and_impact(self, minimal_state, mock_ollama):
        mock_ollama.return_value = _llm_response(
            violations=[{
                "regulation": "GDPR Article 17",
                "description": "No data deletion timeline specified.",
                "likelihood": "high",
                "impact": "high",
            }],
            compliant=False,
        )
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_005", "text": "We may retain user data indefinitely.",
                 "category": "data_privacy", "confidence": 0.9, "risk_flag": True},
            ],
        }

        result = await compliance_agent.run(state)
        violations = result["compliance_results"]["violations"]

        assert result["compliance_results"]["compliant"] is False
        assert len(violations) == 1
        assert violations[0]["likelihood"] == "high"
        assert violations[0]["impact"] == "high"
        assert violations[0]["severity"] == "high"  # derived: high x high = 9 -> high
        assert violations[0]["clause_id"] == "clause_005"

    @pytest.mark.asyncio
    async def test_missing_requirement_has_no_clause_id(self, minimal_state, mock_ollama):
        mock_ollama.return_value = _llm_response(
            missing=["Right to erasure provision"],
            compliant=False,
        )
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_007", "text": "...", "category": "data_privacy",
                 "confidence": 0.9, "risk_flag": False},
            ],
        }

        result = await compliance_agent.run(state)
        # violations = result["compliance_results"]["violations"]

        # assert len(violations) == 1
        # assert violations[0]["clause_id"] is None
        # assert "Right to erasure" in violations[0]["description"]

        missing = result["compliance_results"]["missing_requirements"]

        assert len(missing) == 1
        assert missing[0] == "Right to erasure provision"

    @pytest.mark.asyncio
    async def test_multiple_relevant_clauses_checked_concurrently(self, minimal_state, mock_ollama):
        mock_ollama.side_effect = [
            _llm_response(compliant=True),
            _llm_response(
                violations=[{"regulation": "Internal Policy", "description": "Missing audit clause.",
                             "likelihood": "medium", "impact": "low"}],
                compliant=False,
            ),
        ]
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_001", "text": "...", "category": "confidentiality",
                 "confidence": 0.9, "risk_flag": False},
                {"clause_id": "clause_002", "text": "...", "category": "data_privacy",
                 "confidence": 0.9, "risk_flag": False},
            ],
        }

        result = await compliance_agent.run(state)

        assert len(result["compliance_results"]["violations"]) == 1
        assert result["compliance_results"]["compliant"] is False

    @pytest.mark.asyncio
    async def test_llm_failure_for_one_clause_does_not_crash_others(self, minimal_state, mock_ollama):
        """One clause's check failing should produce a degraded violation entry, not crash the agent."""
        mock_ollama.side_effect = RuntimeError("Ollama timeout")
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_003", "text": "...", "category": "warranty",
                 "confidence": 0.9, "risk_flag": False},
            ],
        }

        result = await compliance_agent.run(state)
        violations = result["compliance_results"]["violations"]

        assert len(violations) == 1
        assert "failed" in violations[0]["description"].lower()
        assert violations[0]["likelihood"] == "medium"  # safe default, not a crash

    @pytest.mark.asyncio
    async def test_result_contains_required_keys(self, minimal_state, mock_ollama):
        mock_ollama.return_value = _llm_response(compliant=True)
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_001", "text": "...", "category": "data_privacy",
                 "confidence": 0.9, "risk_flag": False},
            ],
        }

        result = await compliance_agent.run(state)

        assert "compliance_results" in result
        assert set(result["compliance_results"].keys()) >= {"compliant", "summary", "violations"}
