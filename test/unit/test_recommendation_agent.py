from __future__ import annotations

import json

import pytest

from agents import recommendation_agent


class TestRecommendationAgent:
    @pytest.mark.asyncio
    async def test_generates_recommendations_from_compliance_and_risk(self, rich_state, mock_ollama):
        # LLM refines wording but must map 1:1 onto the deterministic base.
        mock_ollama.return_value = json.dumps({
            "recommendations": [
                {"priority": 1, "clause_id": None,
                 "action": "Add a GDPR Art. 28 data processing clause.",
                 "rationale": "Required for lawful EU data processing."},
                {"priority": 2, "clause_id": "clause_003",
                 "action": "Extend the termination notice period.",
                 "rationale": "30 days is short for this engagement."},
            ]
        })

        result = await recommendation_agent.run(rich_state)

        recommendations = result["recommendations"]
        assert recommendations
        assert recommendations[0]["priority"] == 1
        assert "action" in recommendations[0]
        assert "rationale" in recommendations[0]

    @pytest.mark.asyncio
    async def test_falls_back_to_deterministic_when_llm_malformed(self, rich_state, mock_ollama):
        # Empty/malformed LLM output → deterministic base is used unchanged.
        mock_ollama.return_value = json.dumps({})

        result = await recommendation_agent.run(rich_state)

        recommendations = result["recommendations"]
        assert recommendations
        assert recommendations[0]["priority"] == 1
        assert recommendations[0]["action"]
        assert recommendations[0]["rationale"]

    @pytest.mark.asyncio
    async def test_returns_empty_recommendations_when_inputs_are_clean(self, minimal_state, mock_ollama):
        state = {
            **minimal_state,
            "compliance_results": {"compliant": True, "violations": []},
            "risk_results": {"overall_risk_score": 0.0, "category_risks": {}, "risk_items": []},
        }

        result = await recommendation_agent.run(state)

        assert result["recommendations"] == []
