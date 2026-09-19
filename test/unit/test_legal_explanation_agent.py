from __future__ import annotations

import json

import pytest

from agents import legal_explanation_agent


class TestLegalExplanationAgent:
    @pytest.mark.asyncio
    async def test_builds_explanations_for_recommendations(self, rich_state, mock_ollama):
        mock_ollama.return_value = json.dumps({
            "explanations": [
                {"recommendation_id": 1,
                 "explanation": "This contract handles personal data but lacks a data "
                                "processing clause, which the law requires."},
            ]
        })

        result = await legal_explanation_agent.run(rich_state)

        explanations = result["legal_explanations"]
        assert explanations
        assert explanations[0]["recommendation_id"] == 1
        assert "explanation" in explanations[0]

    @pytest.mark.asyncio
    async def test_falls_back_when_llm_malformed(self, rich_state, mock_ollama):
        mock_ollama.return_value = json.dumps({})

        result = await legal_explanation_agent.run(rich_state)

        explanations = result["legal_explanations"]
        assert explanations
        assert explanations[0]["recommendation_id"] == 1
        assert explanations[0]["explanation"]

    @pytest.mark.asyncio
    async def test_returns_empty_explanations_without_recommendations(self, minimal_state, mock_ollama):
        result = await legal_explanation_agent.run(minimal_state)
        assert result["legal_explanations"] == []
