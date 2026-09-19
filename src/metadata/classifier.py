"""Lightweight contract document classification heuristics."""
from __future__ import annotations

import re
from pathlib import Path

_TYPE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Vendor Agreement", ("vendor agreement", "supplier agreement", "vendor services")),
    ("Service Agreement", ("service agreement", "services agreement", "master services", "msa")),
    ("Employment Agreement", ("employment agreement", "offer letter", "employee agreement")),
    ("NDA", ("non-disclosure", "nondisclosure", "confidentiality agreement", "nda")),
    ("License Agreement", ("license agreement", "licence agreement", "software license", "eula")),
)


def classify_document_type(
    source_path: str | Path,
    *,
    title: str | None = None,
    text_sample: str | None = None,
) -> str:
    """Classify a contract using title and filename heuristics."""
    path = Path(source_path)
    candidates = [title or "", path.stem.replace("_", " ").replace("-", " "), text_sample or ""]
    haystack = " ".join(candidates).lower()
    haystack = re.sub(r"\s+", " ", haystack)

    for document_type, patterns in _TYPE_PATTERNS:
        if any(pattern in haystack for pattern in patterns):
            return document_type
    return "Unknown"

