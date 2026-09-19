"""Citation generation rules for KB metadata."""
from __future__ import annotations

from pathlib import Path


def contract_citation(document_name: str, page_number: int) -> str:
    """Return a contract citation such as 'VendorAgreement.pdf Page 12'."""
    if page_number > 0:
        return f"{document_name} Page {page_number}"
    return document_name


def compliance_citation(
    *,
    regulation: str,
    article: str = "",
    section: str = "",
    source: str = "",
) -> str:
    """Return a compliance citation for regulation, article, or policy sections."""
    normalized = regulation.upper().replace(" ", "")
    if normalized == "GDPR" and article:
        return f"GDPR Article {article}"
    if normalized == "ISO27001" and section:
        return f"ISO27001 Control {section}"
    if normalized == "HIPAA" and section:
        return f"HIPAA {section}"
    if article:
        return f"{regulation} Article {article}"
    if section:
        return f"{regulation} {section}"
    if source:
        return Path(source).name
    return regulation


def risk_citation(rule: dict) -> str:
    """Return the citation declared by a risk rule."""
    citation = str(rule.get("citation", "")).strip()
    if citation:
        return citation
    risk_type = str(rule.get("risk_type", "RISK")).upper().replace(" ", "-")
    return risk_type

