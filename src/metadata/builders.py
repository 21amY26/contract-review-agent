"""Metadata builders for contract, compliance, and risk KB records."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingestion.chunking.splitter import Chunk
from ingestion.parsers._base import ParseResult

from src.metadata.citations import compliance_citation, contract_citation, risk_citation
from src.metadata.classifier import classify_document_type


def stable_id(*parts: object) -> str:
    """Return a deterministic SHA-256 ID for Chroma records."""
    payload = "\n".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class KBRecord:
    """A single document ready for Chroma insertion."""

    id: str
    text: str
    metadata: dict[str, str | int | float | bool]


def build_contract_record(parse_result: ParseResult, chunk: Chunk) -> KBRecord:
    """Build Chroma text and metadata for a contract chunk."""
    source_path = parse_result.source_path
    document_name = source_path.name
    page_number = chunk.page_numbers[0] if chunk.page_numbers else 0
    chunk_id = stable_id(source_path.resolve(), chunk.chunk_index, chunk.text)
    document_type = classify_document_type(
        source_path,
        title=str(parse_result.metadata.get("title", "")),
        text_sample=parse_result.full_text[:1500],
    )

    metadata: dict[str, str | int | float | bool] = {
        "source": str(source_path),
        "document_name": document_name,
        "document_type": document_type,
        "chunk_id": chunk_id,
        "chunk_index": int(chunk.chunk_index),
        "section_id": chunk.section_id or "",
        "heading": chunk.heading or "",
        "page_number": int(page_number),
        "citation": contract_citation(document_name, page_number),
        "is_split_fragment": bool(chunk.is_split_fragment),
        "knowledge_type": "contract",
    }
    return KBRecord(id=chunk_id, text=chunk.text, metadata=metadata)


def build_compliance_record(source_path: Path, chunk: Chunk) -> KBRecord:
    """Build Chroma text and metadata for a compliance chunk."""
    regulation = infer_regulation(source_path)
    article = infer_article(chunk.heading or chunk.text)
    section = infer_section(chunk.heading or chunk.text, regulation=regulation)
    chunk_id = stable_id(source_path.resolve(), chunk.chunk_index, chunk.text)
    metadata: dict[str, str | int | float | bool] = {
        "source": str(source_path),
        "regulation": regulation,
        "article": article,
        "section": section,
        "citation": compliance_citation(
            regulation=regulation,
            article=article,
            section=section,
            source=str(source_path),
        ),
        "knowledge_type": "compliance",
    }
    return KBRecord(id=chunk_id, text=chunk.text, metadata=metadata)


def build_risk_record(rule: dict[str, Any], index: int) -> KBRecord:
    """Build Chroma text and metadata for a risk rule."""
    citation = risk_citation(rule)
    risk_type = str(rule.get("risk_type", "")).strip()
    severity = str(rule.get("severity", "")).strip()
    description = str(rule.get("description", "")).strip()
    text = f"{risk_type}\nSeverity: {severity}\n{description}\nCitation: {citation}".strip()
    record_id = stable_id("risk", citation, risk_type, index)
    metadata: dict[str, str | int | float | bool] = {
        "risk_type": risk_type,
        "severity": severity,
        "citation": citation,
        "knowledge_type": "risk",
    }
    return KBRecord(id=record_id, text=text, metadata=metadata)


def infer_regulation(path: Path) -> str:
    """Infer the compliance source family from the folder or filename."""
    lowered = "/".join(part.lower() for part in path.parts)
    if "gdpr" in lowered:
        return "GDPR"
    if "hipaa" in lowered:
        return "HIPAA"
    if "iso27001" in lowered or "iso-27001" in lowered:
        return "ISO27001"
    if "internal" in lowered:
        return path.stem.replace("_", " ").replace("-", " ").title()
    return "Internal Policy"


def infer_article(text: str) -> str:
    """Extract an article number from a heading or body snippet."""
    match = re.search(r"\bArticle\s+(\d+[A-Za-z]?)\b", text, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def infer_section(text: str, *, regulation: str) -> str:
    """Extract a regulation section or ISO control identifier."""
    if regulation == "ISO27001":
        match = re.search(r"\bA\.\d+(?:\.\d+)*\b", text, flags=re.IGNORECASE)
        if match:
            return match.group(0).upper()

    match = re.search(
        r"\b(?:Section|Control|Policy)\s+([A-Z]?\d+(?:[.\-]\d+)*[A-Z]?)\b",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return ""

