from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents import llm_router


class TestLLMRouter:
    @pytest.mark.asyncio
    async def test_chat_falls_back_to_huggingface_when_groq_and_ollama_fail(self):
        with patch.object(llm_router, "_chat_with_groq", new=AsyncMock(side_effect=RuntimeError("groq down"))), patch.object(
            llm_router, "_chat_with_ollama", new=AsyncMock(side_effect=RuntimeError("ollama down"))
        ), patch.object(
            llm_router, "_chat_with_huggingface", new=AsyncMock(return_value="fallback-response")
        ) as fallback_mock:
            response = await llm_router.chat([{"role": "user", "content": "hello"}])

        assert response == "fallback-response"
        fallback_mock.assert_awaited_once()
