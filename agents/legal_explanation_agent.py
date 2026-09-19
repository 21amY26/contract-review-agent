from __future__ import annotations

import logging
from typing import Any

from agents import llm_router

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a legal explainer for non-lawyers. You are given a list of contract
recommendations. For each one, write a short plain-English explanation (2–3
sentences) of what the issue is and why the recommended action matters, avoiding
legal jargon.

Rules:
- Return EXACTLY one explanation per input recommendation, in the same order.
- Preserve each input's "priority" as "recommendation_id".

Respond ONLY with a JSON object, no prose, no markdown fences:
{
  "explanations": [
    {"recommendation_id": <int>, "explanation": "<plain-English text>"}
  ]
}
"""


def _fallback(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic explanation used when the LLM is unavailable."""
    explanations: list[dict[str, Any]] = []
    for recommendation in recommendations:
        action = recommendation.get("action") or "Address the identified issue"
        rationale = recommendation.get("rationale") or "The clause presents legal or commercial risk."
        explanations.append(
            {
                "recommendation_id": recommendation.get("priority", len(explanations) + 1),
                "explanation": f"{action}. {rationale}",
            }
        )
    return explanations


def _valid(explanations: Any, recommendations: list[dict[str, Any]]) -> bool:
    if not isinstance(explanations, list) or len(explanations) != len(recommendations):
        return False
    return all(isinstance(e, dict) and e.get("explanation") for e in explanations)


async def run(state: dict[str, Any]) -> dict[str, Any]:
    """Translate each recommendation into a plain-English legal explanation.

    Uses the LLM for genuine explanations, falling back to a deterministic
    action+rationale rendering if the LLM is unavailable or malformed.
    """
    recommendations = state.get("recommendations") or []

    if not recommendations:
        return {"legal_explanations": []}

    try:
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"Recommendations:\n{recommendations}"},
        ]
        parsed = await llm_router.chat_json(messages)
        explanations = parsed.get("explanations") if isinstance(parsed, dict) else None
        if _valid(explanations, recommendations):
            # Re-anchor recommendation_id from the trusted recommendations.
            for out, src in zip(explanations, recommendations):
                out["recommendation_id"] = src.get("priority", out.get("recommendation_id"))
            return {"legal_explanations": explanations}
        logger.info("legal explanation LLM output rejected; using deterministic fallback")
    except Exception as exc:
        logger.warning("legal explanation LLM failed, using fallback: %s", exc)

    return {"legal_explanations": _fallback(recommendations)}
