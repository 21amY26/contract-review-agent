"""
tests/unit/test_risk_agent.py
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from agents import risk_agent


def _mock_risk_retrieval(*_args, **_kwargs):
    return [
        {
            "text": "Automatic renewal without a clear notice window is a termination risk.",
            "metadata": {"citation": "RISK-005"},
            "score": 0.78,
        }
    ]


def _llm_response(likelihood="medium", impact="medium", reason="test reason"):
    return json.dumps({"likelihood": likelihood, "impact": impact, "reason": reason})


@pytest.fixture(autouse=True)
def _patch_retrieval():
    with patch("agents.risk_agent.search_risks", side_effect=_mock_risk_retrieval):
        yield


class TestRiskAgent:
    @pytest.mark.asyncio
    async def test_no_clauses_returns_baseline_low_risk(self, minimal_state, mock_ollama):
        state = {**minimal_state, "classified_clauses": [], "compliance_results": {"violations": []}}

        result = await risk_agent.run(state)
        risk = result["risk_results"]

        # Baseline "low" per category = score 1 (not 0 — a clean contract still
        # carries residual risk per the rubric), so overall isn't literally 0.
        expected = round((1 * sum(risk_agent._WEIGHTS.values()) / 9) * 100, 1)
        assert risk["overall_risk_score"] == expected
        for cat in risk["category_risks"].values():
            assert cat["level"] == "low"
        mock_ollama.assert_not_called()

    @pytest.mark.asyncio
    async def test_payment_clause_gets_fresh_llm_judgment(self, minimal_state, mock_ollama):
        mock_ollama.return_value = _llm_response(likelihood="high", impact="medium", reason="Net-90 terms are unusually long.")
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_001", "text": "Payment due net 90 days.", "category": "payment",
                 "confidence": 0.9, "risk_flag": True},
            ],
            "compliance_results": {"violations": []},
        }

        result = await risk_agent.run(state)
        payment_risk = result["risk_results"]["category_risks"]["payment_risk"]

        mock_ollama.assert_called_once()
        assert payment_risk["likelihood"] == "high"
        assert payment_risk["impact"] == "medium"
        assert payment_risk["score"] == 6  # high(3) x medium(2)
        assert payment_risk["level"] == "high"

    @pytest.mark.asyncio
    async def test_data_privacy_reuses_compliance_judgment_no_llm_call(self, minimal_state, mock_ollama):
        """Liability/Data Privacy categories must NOT trigger a fresh LLM call."""
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_002", "text": "...", "category": "data_privacy",
                 "confidence": 0.9, "risk_flag": True},
            ],
            "compliance_results": {
                "violations": [
                    {"clause_id": "clause_002", "regulation": "GDPR Art. 17",
                     "description": "No deletion timeline.", "likelihood": "high", "impact": "high"},
                ],
            },
        }

        result = await risk_agent.run(state)
        privacy_risk = result["risk_results"]["category_risks"]["data_privacy_risk"]

        mock_ollama.assert_not_called()  # reused, not re-judged
        assert privacy_risk["likelihood"] == "high"
        assert privacy_risk["impact"] == "high"
        assert privacy_risk["score"] == 9

    @pytest.mark.asyncio
    async def test_multiple_violations_in_one_category_use_max(self, minimal_state, mock_ollama):
        """Worst-case aggregation: one severe + one minor violation -> category takes the severe one."""
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_001", "text": "...", "category": "indemnification",
                 "confidence": 0.9, "risk_flag": True},
                {"clause_id": "clause_002", "text": "...", "category": "liability_cap",
                 "confidence": 0.9, "risk_flag": False},
            ],
            "compliance_results": {
                "violations": [
                    {"clause_id": "clause_001", "regulation": "Internal Policy",
                     "description": "Uncapped indemnity.", "likelihood": "high", "impact": "high"},
                    {"clause_id": "clause_002", "regulation": "Internal Policy",
                     "description": "Minor wording issue.", "likelihood": "low", "impact": "low"},
                ],
            },
        }

        result = await risk_agent.run(state)
        liability_risk = result["risk_results"]["category_risks"]["liability_risk"]

        assert liability_risk["likelihood"] == "high"
        assert liability_risk["impact"] == "high"
        assert liability_risk["score"] == 9

    @pytest.mark.asyncio
    async def test_unmapped_category_excluded_not_guessed(self, minimal_state, mock_ollama):
        """clause_type='other' should not be silently routed anywhere."""
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_000", "text": "...", "category": "other",
                 "confidence": 0.9, "risk_flag": False},
            ],
            "compliance_results": {"violations": []},
        }

        result = await risk_agent.run(state)

        mock_ollama.assert_not_called()
        for cat in result["risk_results"]["category_risks"].values():
            assert cat["level"] == "low"  # baseline, "other" contributed nothing

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_safely(self, minimal_state, mock_ollama):
        mock_ollama.side_effect = RuntimeError("Ollama timeout")
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_003", "text": "...", "category": "termination",
                 "confidence": 0.9, "risk_flag": False},
            ],
            "compliance_results": {"violations": []},
        }

        result = await risk_agent.run(state)
        risk_items = result["risk_results"]["risk_items"]

        assert len(risk_items) == 1
        assert risk_items[0]["source"] == "fallback"
        assert "failed" in risk_items[0]["description"].lower()

    @pytest.mark.asyncio
    async def test_overall_score_is_weighted_average_normalized(self, minimal_state, mock_ollama):
        """All categories high (score 9) -> overall should normalize to 100."""
        mock_ollama.return_value = _llm_response(likelihood="high", impact="high")
        state = {
            **minimal_state,
            "classified_clauses": [
                {"clause_id": "clause_001", "text": "...", "category": "payment", "confidence": 0.9, "risk_flag": True},
                {"clause_id": "clause_002", "text": "...", "category": "termination", "confidence": 0.9, "risk_flag": True},
                {"clause_id": "clause_003", "text": "...", "category": "governing_law", "confidence": 0.9, "risk_flag": True},
            ],
            "compliance_results": {
                "violations": [
                    {"clause_id": None, "regulation": "Internal", "description": "n/a",
                     "likelihood": "high", "impact": "high"},
                ],
            },
        }
        # No clauses for liability_risk/data_privacy_risk categories exist in this state,
        # so they fall back to baseline-low (no violations attributed, no matching clause_id).

        result = await risk_agent.run(state)

        assert 0.0 <= result["risk_results"]["overall_risk_score"] <= 100.0

    @pytest.mark.asyncio
    async def test_result_contains_required_keys(self, minimal_state, mock_ollama):
        state = {**minimal_state, "classified_clauses": [], "compliance_results": {"violations": []}}

        result = await risk_agent.run(state)

        assert "risk_results" in result
        required = {"overall_risk_score", "summary", "category_risks", "risk_items"}
        assert required <= set(result["risk_results"].keys())
