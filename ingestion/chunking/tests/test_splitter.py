"""
Tests for ingestion.chunking.splitter

Run with:
    pytest ingestion/chunking/tests/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make project root importable when run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ingestion.chunking.splitter import chunk_parse_result, _split_into_blocks
from ingestion.parsers import DOCXParser, PDFParser

_DATA_DIR = Path(__file__).resolve().parents[3] / "ingestion" / "parsers" / "tests" / "data"
_SAMPLE_DOCX = _DATA_DIR / "sample_report.docx"
_SAMPLE_PDF = _DATA_DIR / "sample_report.pdf"


# ---------------------------------------------------------------------------
# Unit tests on the block-splitting regex logic (no real files needed)
# ---------------------------------------------------------------------------

class TestSplitIntoBlocks:

    def test_markdown_heading_boundary(self):
        text = "# Title\nSome intro text.\n## Section One\nBody text here."
        blocks = _split_into_blocks(text)
        headings = [b.heading for b in blocks]
        assert "Title" in headings
        assert "Section One" in headings

    def test_numbered_clause_boundary(self):
        text = (
            "1.1 Confidential Information means non-public data.\n"
            "1.2 Effective Date means the date above.\n"
        )
        blocks = _split_into_blocks(text)
        ids = [b.section_id for b in blocks]
        assert "1.1" in ids
        assert "1.2" in ids

    def test_table_placeholder_tracked(self):
        text = "## Pricing\nSee table below.\n[TABLE 1]\nMore text after."
        blocks = _split_into_blocks(text)
        # the block containing the placeholder should record table_refs
        assert any(b.table_refs == [0] for b in blocks)

    def test_no_boundaries_returns_single_block(self):
        text = "Just plain prose with no numbering or headings at all."
        blocks = _split_into_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].section_id is None
        assert blocks[0].heading is None


# ---------------------------------------------------------------------------
# Integration tests against real sample files
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestChunkRealFiles:

    def test_docx_chunking(self):
        if not _SAMPLE_DOCX.exists():
            pytest.skip(f"Sample file missing: {_SAMPLE_DOCX}")

        result = DOCXParser().parse(_SAMPLE_DOCX)
        chunks = chunk_parse_result(result, source_name="sample_report.docx")

        assert len(chunks) > 0
        # at least one chunk should carry a heading (from the # markers)
        assert any(c.heading for c in chunks)
        # chunk text should never be empty
        assert all(c.text.strip() for c in chunks)

    def test_pdf_chunking(self):
        if not _SAMPLE_PDF.exists():
            pytest.skip(f"Sample file missing: {_SAMPLE_PDF}")

        result = PDFParser().parse(_SAMPLE_PDF)
        chunks = chunk_parse_result(result, source_name="sample_report.pdf")

        assert len(chunks) > 0
        assert all(c.text.strip() for c in chunks)
        # PDF chunks should carry page numbers; DOCX chunks generally won't
        assert all(c.page_numbers for c in chunks if c.page_numbers is not None)

    def test_chunk_sizes_within_bound(self):
        if not _SAMPLE_PDF.exists():
            pytest.skip(f"Sample file missing: {_SAMPLE_PDF}")

        result = PDFParser().parse(_SAMPLE_PDF)
        chunks = chunk_parse_result(result, source_name="sample_report.pdf", max_tokens=500)

        # stage-2 fallback should keep fragments roughly within bound
        # (allow slack since char/4 is an approximation, not a real tokenizer)
        oversized = [c for c in chunks if len(c.text) // 4 > 700]
        assert len(oversized) == 0, f"{len(oversized)} chunk(s) exceeded expected size"
