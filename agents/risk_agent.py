
from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents import llm_router
from agents.schemas import CategoryRisk, RiskItem, RiskOutput
from src.retrieval.retriever import search_risks

logger = logging.getLogger(__name__)

# clause category -> risk category. "other" and unmapped categories are
# excluded deliberately rather than silently guessed.
_CATEGORY_TO_RISK = {
    "indemnification":    "liability_risk",
    "liability_cap":      "liability_risk",
    "ip_ownership":       "liability_risk",    # pending: confirm policy coverage
    "warranty":           "liability_risk",    # pending: confirm policy coverage
    "force_majeure":      "liability_risk",    # pending: team confirmation
    "data_privacy":       "data_privacy_risk",
    "confidentiality":    "data_privacy_risk",
    "payment":            "payment_risk",
    "termination":        "termination_risk",
    "auto_renewal":       "termination_risk",
    "governing_law":      "jurisdiction_risk",
    "dispute_resolution": "jurisdiction_risk",
}

# Categories whose likelihood/impact is reused from compliance_results
# rather than judged fresh by this agent.
_REUSED_FROM_COMPLIANCE = {"liability_risk", "data_privacy_risk"}

_RISK_CATEGORIES = (
    "liability_risk",
    "data_privacy_risk",
    "payment_risk",
    "termination_risk",
    "jurisdiction_risk",
)

# Placeholder weights — needs business sign-off, not just engineering judgment.
_WEIGHTS = {
    "liability_risk": 0.25,
    "data_privacy_risk": 0.25,
    "payment_risk": 0.15,
    "termination_risk": 0.20,
    "jurisdiction_risk": 0.15,
}

_LIKELIHOOD_SCORE = {"low": 1, "medium": 2, "high": 3}
_IMPACT_SCORE = {"low": 1, "medium": 2, "high": 3}

_SYSTEM = """\
You are a contract risk analyst.

You will be given one contract clause and, if available, relevant risk
rules retrieved from a risk knowledge base.

Task: judge the likelihood and impact of this clause being a business risk.
- likelihood: how likely this is to actually cause a real problem in
  practice ("low", "medium", or "high")
- impact: how severe the consequences would be if it does ("low",
  "medium", or "high")

Respond ONLY with a JSON object, no prose, no markdown fences, matching
this schema:
{
  "likelihood": "low" | "medium" | "high",
  "impact": "low" | "medium" | "high",
  "reason": "<short explanation>"
}
"""


async def _judge_one_clause(clause: dict[str, Any], contract_id: str) -> RiskItem:
    clause_text = clause.get("text", "")
    clause_id = clause.get("clause_id")
    risk_category = _CATEGORY_TO_RISK.get(clause.get("category", ""), "")

    try:
        retrieved = search_risks(clause_text, n_results=3)
        context = "\n\n".join(
            f"[{r['metadata'].get('citation', 'Unknown')}] {r['text']}"
            for r in retrieved
        )
        messages = [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Clause:\n{clause_text}\n\n"
                    f"Relevant risk rules (if any):\n{context if context else '(none found)'}"
                ),
            },
        ]
        parsed = await llm_router.chat_json(messages)
        return RiskItem(
            clause_id=clause_id,
            risk_type=risk_category,
            likelihood=parsed.get("likelihood", "medium"),
            impact=parsed.get("impact", "medium"),
            description=parsed.get("reason", ""),
            source="risk_agent",
        )
    except Exception as exc:
        logger.warning("[%s] risk judgment failed for %s: %s", contract_id, clause_id, exc)
        return RiskItem(
            clause_id=clause_id,
            risk_type=risk_category,
            likelihood="medium",
            impact="medium",
            description=f"Risk judgment failed: {exc}",
            source="fallback",
        )


def _judgments_from_compliance(
    risk_category: str,
    clauses: list[dict[str, Any]],
    compliance_results: dict[str, Any],
) -> list[RiskItem]:
    """Reuse likelihood/impact already produced by compliance_agent."""
    clause_ids = {c.get("clause_id") for c in clauses}
    judgments: list[RiskItem] = []

    for violation in compliance_results.get("violations", []):
        # None clause_id means "applies to the contract generally" (e.g. a
        # missing required clause) — still attribute it here if any clause
        # of this category exists, since there's nowhere else for it to go.
        if violation.get("clause_id") in clause_ids or (violation.get("clause_id") is None and clauses):
            judgments.append(
                RiskItem(
                    clause_id=violation.get("clause_id"),
                    risk_type=risk_category,
                    likelihood=violation.get("likelihood", "low"),
                    impact=violation.get("impact", "low"),
                    description=violation.get("description", ""),
                    source="compliance_agent",
                )
            )

    if not judgments and clauses:
        # Clauses of this category exist but no violations were flagged —
        # treat as clean, baseline-low risk (not zero — see scoring rubric).
        judgments.append(
            RiskItem(
                clause_id=None,
                risk_type=risk_category,
                likelihood="low",
                impact="low",
                description="No compliance issues found for this category.",
                source="compliance_agent",
            )
        )

    return judgments


def _aggregate_category(judgments: list[RiskItem]) -> CategoryRisk:
    """Combine multiple judgments in a category via max (worst-case-driven)."""
    if not judgments:
        likelihood, impact, reasons = "low", "low", []
    else:
        likelihood = max((j.likelihood for j in judgments), key=lambda lv: _LIKELIHOOD_SCORE.get(lv, 2))
        impact = max((j.impact for j in judgments), key=lambda iv: _IMPACT_SCORE.get(iv, 2))
        reasons = [j.description for j in judgments if j.description]

    score = _LIKELIHOOD_SCORE.get(likelihood, 1) * _IMPACT_SCORE.get(impact, 1)
    level = "low" if score <= 2 else "medium" if score <= 4 else "high"

    return CategoryRisk(likelihood=likelihood, impact=impact, score=score, level=level, reasons=reasons)


def _overall_score(category_risks: dict[str, CategoryRisk]) -> float:
    """Weighted aggregation across all 5 categories, normalized to 0-100."""
    weighted = sum(category_risks[cat].score * _WEIGHTS[cat] for cat in _RISK_CATEGORIES)
    max_possible = 9  # max score per category from the likelihood x impact matrix
    return round((weighted / max_possible) * 100, 1)


def _summarize(category_risks: dict[str, CategoryRisk]) -> str:
    high_risk = [cat for cat in _RISK_CATEGORIES if category_risks[cat].level == "high"]
    if not high_risk:
        return "No high-risk categories identified."
    readable = ", ".join(cat.replace("_", " ") for cat in high_risk)
    return f"High risk identified in: {readable}."


async def run(state: dict[str, Any]) -> dict[str, Any]:
    """Compute per-category and overall risk scores for the contract."""
    contract_id: str = state.get("contract_id", "unknown")
    classified_clauses: list[dict[str, Any]] = state.get("classified_clauses") or []
    compliance_results: dict[str, Any] = state.get("compliance_results") or {"violations": []}

    clauses_by_category: dict[str, list[dict[str, Any]]] = {cat: [] for cat in _RISK_CATEGORIES}
    for clause in classified_clauses:
        risk_category = _CATEGORY_TO_RISK.get(clause.get("category", ""))
        if risk_category:
            clauses_by_category[risk_category].append(clause)

    # Gather all fresh-judgment LLM calls concurrently across every
    # non-reused category at once (mirrors clause_classification_agent's pattern).
    fresh_categories = [cat for cat in _RISK_CATEGORIES if cat not in _REUSED_FROM_COMPLIANCE]
    fresh_clause_pairs = [
        (cat, clause) for cat in fresh_categories for clause in clauses_by_category[cat]
    ]
    fresh_results = await asyncio.gather(
        *[_judge_one_clause(clause, contract_id) for _, clause in fresh_clause_pairs]
    )

    judgments_by_category: dict[str, list[RiskItem]] = {cat: [] for cat in _RISK_CATEGORIES}
    for (cat, _), item in zip(fresh_clause_pairs, fresh_results, strict=False):
        judgments_by_category[cat].append(item)

    for cat in _REUSED_FROM_COMPLIANCE:
        judgments_by_category[cat] = _judgments_from_compliance(
            cat, clauses_by_category[cat], compliance_results
        )

    category_risks: dict[str, CategoryRisk] = {
        cat: _aggregate_category(judgments_by_category[cat]) for cat in _RISK_CATEGORIES
    }
    all_items = [item for cat in _RISK_CATEGORIES for item in judgments_by_category[cat]]
    overall_score = _overall_score(category_risks)

    output = RiskOutput(
        overall_risk_score=overall_score,
        summary=_summarize(category_risks),
        category_risks=category_risks,
        risk_items=all_items,
    )

    logger.info(
        "[%s] risk_agent → overall_score=%.1f, %d risk item(s)",
        contract_id, overall_score, len(all_items),
    )

    return {"risk_results": output.model_dump()}
