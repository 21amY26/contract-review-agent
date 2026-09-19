from __future__ import annotations

import asyncio
import logging
from typing import Any



from agents import llm_router
from agents.schemas import ComplianceOutput, ComplianceViolation
from src.retrieval.retriever import search_compliance

logger = logging.getLogger(__name__)

# Only these clause categories get checked against the compliance KB.
# Business-risk-only categories are handled by risk_agent.
_COMPLIANCE_RELEVANT_CATEGORIES = {
    "data_privacy",
    "confidentiality",
    "ip_ownership",
    "warranty",
}

_SYSTEM = """\
You are a legal compliance reviewer.

You will be given:

1. A SINGLE contract clause.
2. Several retrieved excerpts from regulations and company policies that are relevant to this clause.

IMPORTANT:

If a requirement belongs in another clause of the contract,
do NOT report it as either a violation or a missing requirement.
Only evaluate whether this clause correctly implements the obligation it is intended to address.

Do NOT assume this clause is the entire contract.

Do NOT expect unrelated contractual obligations to appear in this clause.

For example:
- If the clause discusses data deletion, evaluate only deletion-related obligations.
- Do NOT report missing security controls, audit rights, subprocessors, confidentiality clauses, or other unrelated requirements unless they are directly relevant to this clause.

Only report a violation if:
- the clause explicitly contradicts a regulatory requirement, OR
- the clause is clearly insufficient for the specific obligation it is attempting to address.

If a related requirement would normally accompany this clause but is simply absent, list it under "missing_requirements" instead of "violations".

Only reference regulations that appear in the retrieved excerpts.
Do NOT invent regulations or citations.

Respond ONLY with JSON matching:

{
  "violations": [
    {
      "regulation": "...",
      "description": "...",
      "likelihood": "low|medium|high",
      "impact": "low|medium|high"
    }
  ],
  "missing_requirements": [
      "..."
  ]
}
"""

_LIKELIHOOD_SCORE = {"low": 1, "medium": 2, "high": 3}
_IMPACT_SCORE = {"low": 1, "medium": 2, "high": 3}


def _severity_from_likelihood_impact(likelihood: str, impact: str) -> str:
    """Deterministic severity bucket from the likelihood × impact matrix."""
    score = (
        _LIKELIHOOD_SCORE.get(likelihood, 2)
        * _IMPACT_SCORE.get(impact, 2)
    )

    if score <= 2:
        return "low"
    if score <= 4:
        return "medium"
    return "high"


async def _check_clause(
    clause: dict[str, Any],
    contract_id: str,
) -> dict[str, Any]:
    """
    Retrieve relevant policy text and evaluate one clause.

    Returns:
    {
        "violations": list[ComplianceViolation],
        "missing_requirements": list[str]
    }
    """

    clause_text = clause.get("text", "")
    clause_id = clause.get("clause_id")

    try:
        retrieved = search_compliance(
            clause_text,
            n_results=3,
        )

        # print(f"\n========== RETRIEVED for {clause_id} ==========")
        # for r in retrieved:
            # print(
            #     f"  {r['metadata'].get('citation', 'NO CITATION')} "
            #     f"| score={r['score']:.3f}"
            # )

        context = "\n\n".join(
            f"[{r['metadata'].get('citation', 'Unknown source')}]\n{r['text']}"
            for r in retrieved
        )

        messages = [
            {
                "role": "system",
                "content": _SYSTEM,
            },
            {
                "role": "user",
                "content": (
                    f"Clause:\n{clause_text}\n\n"
                    f"Retrieved policy/regulation excerpts:\n"
                    f"{context if context else '(none found)'}"
                ),
            },
        ]

        parsed = await llm_router.chat_json(messages)

        # print(f"\n========== RAW LLM for {clause_id} ==========")
        # pprint(parsed)

    except Exception as exc:
        logger.warning(
            "[%s] compliance check failed for %s: %s",
            contract_id,
            clause_id,
            exc,
        )

        return {
            "violations": [
                ComplianceViolation(
                    clause_id=clause_id,
                    regulation="",
                    description=f"Compliance check failed: {exc}",
                    likelihood="medium",
                    impact="medium",
                    severity="medium",
                )
            ],
            "missing_requirements": [],
        }

    violations: list[ComplianceViolation] = []

    for v in parsed.get("violations", []):

        likelihood = v.get("likelihood", "medium")
        impact = v.get("impact", "medium")

        violations.append(
            ComplianceViolation(
                clause_id=clause_id,
                regulation=v.get("regulation", ""),
                description=v.get("description", ""),
                likelihood=likelihood,
                impact=impact,
                severity=_severity_from_likelihood_impact(
                    likelihood,
                    impact,
                ),
            )
        )

    return {
        "violations": violations,
        "missing_requirements": parsed.get(
            "missing_requirements",
            [],
        ),
    }


async def run(state: dict[str, Any]) -> dict[str, Any]:
    """Check compliance-relevant clauses."""

    contract_id: str = state.get(
        "contract_id",
        "unknown",
    )

    classified_clauses: list[dict[str, Any]] = (
        state.get("classified_clauses") or []
    )

    relevant_clauses = [
        clause
        for clause in classified_clauses
        if clause.get("category") in _COMPLIANCE_RELEVANT_CATEGORIES
    ]

    if not relevant_clauses:

        output = ComplianceOutput(
            compliant=True,
            summary="No compliance-relevant clauses found.",
            violations=[],
            missing_requirements=[],
        )

        return {
            "compliance_results": output.model_dump()
        }

    results = await asyncio.gather(
        *[
            _check_clause(
                clause,
                contract_id,
            )
            for clause in relevant_clauses
        ]
    )

    all_violations: list[ComplianceViolation] = []
    all_missing_requirements: list[str] = []

    for result in results:
        all_violations.extend(result["violations"])
        all_missing_requirements.extend(
            result["missing_requirements"]
        )
    all_missing_requirements = list(dict.fromkeys(all_missing_requirements))
    compliant = len(all_violations) == 0

    if compliant:
        summary = "No compliance violations found."
    else:
        summary = (
            f"{len(all_violations)} compliance violation(s) found. "
            f"{len(all_missing_requirements)} missing requirement(s) identified."
        )

    output = ComplianceOutput(
        compliant=compliant,
        summary=summary,
        violations=all_violations,
        missing_requirements=all_missing_requirements,
    )

    logger.info(
        "[%s] compliance_agent → %d clause(s) checked, %d violation(s)",
        contract_id,
        len(relevant_clauses),
        len(all_violations),
    )

    return {
        "compliance_results": output.model_dump()
    }