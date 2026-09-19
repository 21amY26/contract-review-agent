"""
agents/llm_router.py

Async LLM router with a local Ollama path and a free Hugging Face fallback.
The default behaviour is to try Ollama first, then fall back to a public
Hugging Face inference endpoint so the agents can still run when Ollama is
not available.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()  

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

if not GROQ_API_KEY:
    logger.warning(
        "GROQ_API_KEY is not set — Groq calls will fail and the router will "
        "fall back to Ollama, then Hugging Face. Set it in .env or the "
        "environment to use Groq."
    )
HF_MODEL: str = os.getenv("HF_MODEL", "microsoft/Phi-3.5-mini-instruct")
HF_API_URL: str = os.getenv(
    "HF_API_URL",
    f"https://api-inference.huggingface.co/models/{HF_MODEL}",
)
HF_API_TOKEN: str | None = os.getenv("HF_API_TOKEN")

# Per-request timeout: generous because local models can be slow.
_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
    """Convert OpenAI-style chat messages to a single prompt string."""
    parts: list[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            parts.append(f"System: {content}")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(f"User: {content}")
    parts.append("Assistant:")
    return "\n".join(parts)


async def _chat_with_ollama(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    format: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "model": model or OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if format:
        payload["format"] = format
    if extra:
        payload.update(extra)

    url = f"{OLLAMA_BASE_URL}/api/chat"
    logger.debug("Ollama → %s | %d message(s)", payload["model"], len(messages))

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()

    body = resp.json()
    content: str = body["message"]["content"]
    logger.debug("Ollama ← %d chars", len(content))
    return content


async def _chat_with_groq(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    format: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "model": model or GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if format == "json":
        payload["response_format"] = {"type": "json_object"}
    if extra:
        payload.update(extra)

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    url = "https://api.groq.com/openai/v1/chat/completions"
    logger.debug("Groq → %s | %d message(s)", payload["model"], len(messages))

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()

    body = resp.json()
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError(f"Unexpected Groq response: {body}")
    content: str = choices[0].get("message", {}).get("content", "")
    if not isinstance(content, str):
        raise RuntimeError(f"Unexpected Groq content format: {body}")
    return content


async def _chat_with_huggingface(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    format: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    prompt = _messages_to_prompt(messages)
    if format == "json":
        prompt = f"{prompt}\nReturn only valid JSON."

    payload: dict[str, Any] = {
        "inputs": prompt,
        "parameters": {
            "temperature": temperature,
            "max_new_tokens": 512,
            "return_full_text": False,
        },
        "options": {"wait_for_model": True},
    }
    if extra:
        payload.update(extra)

    headers = {"Content-Type": "application/json"}
    if HF_API_TOKEN:
        headers["Authorization"] = f"Bearer {HF_API_TOKEN}"

    url = model and f"https://api-inference.huggingface.co/models/{model}" or HF_API_URL
    logger.debug("Hugging Face → %s | %d message(s)", url, len(messages))

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()

    body = resp.json()
    if isinstance(body, list) and body:
        generated = body[0].get("generated_text", "")
        if isinstance(generated, str):
            return generated.strip()
    if isinstance(body, dict):
        generated = body.get("generated_text") or body.get("output_text") or ""
        if isinstance(generated, str):
            return generated.strip()

    raise RuntimeError(f"Unexpected Hugging Face response: {body}")


async def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    format: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Send a chat request to Groq first, then fall back to Ollama and Hugging Face."""
    try:
        return await _chat_with_groq(
            messages,
            model=model,
            temperature=temperature,
            format=format,
            extra=extra,
        )
    except Exception as exc:
        logger.warning("Groq failed, trying Ollama: %s", exc)

    try:
        return await _chat_with_ollama(
            messages,
            model=model,
            temperature=temperature,
            format=format,
            extra=extra,
        )
    except Exception as exc:
        logger.warning("Ollama failed, trying Hugging Face: %s", exc)

    try:
        return await _chat_with_huggingface(
            messages,
            model=model,
            temperature=temperature,
            format=format,
            extra=extra,
        )
    except Exception as exc:
        logger.exception("Hugging Face fallback failed: %s", exc)
        if format == "json":
            return "{}"
        return "Fallback response unavailable."


async def chat_json(
    messages: list[dict[str, str]],
    **kwargs,
) -> Any:
    """Like ``chat()``, but parses the response as JSON and returns the object."""
    raw = await chat(messages, format="json", **kwargs)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start : end + 1])
        raise


# ----------------------------------------------------------------------
# Compatibility wrapper for agents expecting get_structured_llm()
# ----------------------------------------------------------------------


class StructuredLLM:
    def __init__(self, schema: type[BaseModel]):
        self.schema = schema

    async def ainvoke(self, messages):
        data = await chat_json(messages)
        return self.schema.model_validate(data)


def get_structured_llm(schema: type[BaseModel]):
    return StructuredLLM(schema)
