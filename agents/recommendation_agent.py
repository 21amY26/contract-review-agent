from __future__ import annotations

import logging
from typing import Any

from agents import llm_router

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a contract negotiation advisor. You are given a list of draft
recommendations derived from compliance violations and business risks found in
a contract. Rewrite each into a clear, specific, actionable recommendation for
the reviewing lawyer.

Rules:
- Return EXACTLY one output recommendation per input recommendation, in the same
  order, preserving each input's "priority" and "clause_id" unchanged.
- "action" must be an imperative, concrete step (what to add/change/negotiate).
- "rationale" must briefly explain why, referencing the underlying issue.
- Do NOT invent new issues or drop any input.

Respond ONLY with a JSON object, no prose, no markdown fences:
{
  "recommendations": [
    {"priority": <int>, "clause_id": <string|null>, "action": "<str>", "rationale": "<str>"}
  ]
}
"""


def _build_deterministic(compliance_results: dict, risk_results: dict) -> list[dict[str, Any]]:
    """Ground-truth recommendations derived directly from findings. Always
    available as the guaranteed fallback if the LLM is unavailable."""
    recommendations: list[dict[str, Any]] = []

    violations = compliance_results.get("violations") or []
    for idx, violation in enumerate(violations, start=1):
        action = (
            f"Address the compliance issue in {violation.get('regulation') or 'the contract'}"
            if violation.get("regulation")
            else "Address the identified compliance issue"
        )
        recommendations.append(
            {
                "priority": idx,
                "clause_id": violation.get("clause_id"),
                "action": action,
                "rationale": violation.get("description") or "Compliance issue requires remediation.",
            }
        )

    risk_items = risk_results.get("risk_items") or []
    for item in risk_items:
        if not any(rec.get("clause_id") == item.get("clause_id") for rec in recommendations):
            recommendations.append(
                {
                    "priority": len(recommendations) + 1,
                    "clause_id": item.get("clause_id"),
                    "action": "Mitigate the identified business risk in the clause.",
                    "rationale": item.get("description") or "Business risk requires mitigation.",
                }
            )

    recommendations.sort(key=lambda item: item.get("priority", 999))
    return recommendations


def _valid_refinement(refined: Any, base: list[dict[str, Any]]) -> bool:
    """Only accept LLM output that maps 1:1 onto the deterministic base."""
    if not isinstance(refined, list) or len(refined) != len(base):
        return False
    return all(
        isinstance(r, dict) and r.get("action") and r.get("rationale")
        for r in refined
    )


async def run(state: dict[str, Any]) -> dict[str, Any]:
    """Turn compliance and risk findings into actionable recommendations.

    Deterministic findings form the guaranteed base; an LLM pass refines the
    wording. If the LLM is unavailable or returns malformed output, the
    deterministic base is used unchanged.
    """
    compliance_results = state.get("compliance_results") or {}
    risk_results = state.get("risk_results") or {}

    base = _build_deterministic(compliance_results, risk_results)
    if not base:
        return {"recommendations": []}

    try:
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"Draft recommendations:\n{base}"},
        ]
        parsed = await llm_router.chat_json(messages)
        refined = parsed.get("recommendations") if isinstance(parsed, dict) else None
        if _valid_refinement(refined, base):
            # Re-anchor priority/clause_id from the trusted base by position.
            for out, src in zip(refined, base):
                out["priority"] = src["priority"]
                out["clause_id"] = src.get("clause_id")
            refined.sort(key=lambda item: item.get("priority", 999))
            return {"recommendations": refined}
        logger.info("recommendation LLM output rejected; using deterministic base")
    except Exception as exc:
        logger.warning("recommendation LLM refinement failed, using base: %s", exc)

    return {"recommendations": base}
