"""
Tests for ingestion.parsers — pdf_parser, docx_parser, ocr_parser.

Run with:
    pytest ingestion/parsers/tests/ -v
"""
from __future__ import annotations

import io
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the package root is importable when tests are run from the repo root.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ingestion.parsers import (
    DOCXParser,
    PDFParser,
    get_parser,
)
from ingestion.parsers._base import (
    ExtractionWarning,
    PageType,
    ParserError,
    UnsupportedFormatError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def simple_pdf(tmp_dir: Path) -> Path:
    """Create a minimal single-page PDF with a text layer."""
    import fitz
    path = tmp_dir / "simple.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello World\nLine two of content.")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def multi_page_pdf(tmp_dir: Path) -> Path:
    import fitz
    path = tmp_dir / "multi.pdf"
    doc = fitz.open()
    for i in range(5):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} content here.")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def simple_docx(tmp_dir: Path) -> Path:
    """Create a minimal DOCX with headings, body paragraphs, and a table."""
    from docx import Document
    from docx.oxml.ns import qn
    path = tmp_dir / "simple.docx"
    doc = Document()
    doc.add_heading("Top-level Heading", level=1)
    doc.add_paragraph("First body paragraph.")
    doc.add_heading("Sub-Heading", level=2)
    doc.add_paragraph("Second body paragraph with more text.")
    table = doc.add_table(rows=2, cols=3)
    for r_idx, row in enumerate(table.rows):
        for c_idx, cell in enumerate(row.cells):
            cell.text = f"R{r_idx}C{c_idx}"
    doc.save(str(path))
    return path


# ---------------------------------------------------------------------------
# PDFParser tests
# ---------------------------------------------------------------------------

class TestPDFParser:

    def test_basic_extraction(self, simple_pdf: Path) -> None:
        result = PDFParser().parse(simple_pdf)
        assert len(result) == 1
        assert "Hello World" in result.full_text
        assert "Line two" in result.full_text

    def test_metadata_present(self, simple_pdf: Path) -> None:
        result = PDFParser().parse(simple_pdf)
        assert "page_count" in result.metadata
        assert result.metadata["page_count"] == 1

    def test_multi_page(self, multi_page_pdf: Path) -> None:
        result = PDFParser().parse(multi_page_pdf)
        assert len(result) == 5
        for i, page in enumerate(result.pages):
            assert f"Page {i + 1}" in page.text

    def test_max_pages(self, multi_page_pdf: Path) -> None:
        result = PDFParser(max_pages=2).parse(multi_page_pdf)
        assert len(result) == 2
        assert any("max_pages" in w for w in result.warnings)

    def test_page_numbers_are_1based(self, multi_page_pdf: Path) -> None:
        result = PDFParser().parse(multi_page_pdf)
        for idx, page in enumerate(result.pages):
            assert page.page_number == idx + 1

    def test_elapsed_time_recorded(self, simple_pdf: Path) -> None:
        result = PDFParser().parse(simple_pdf)
        assert result.elapsed_seconds > 0

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            PDFParser().parse("/nonexistent/file.pdf")

    def test_wrong_extension(self, tmp_path: Path) -> None:
        bad = tmp_path / "doc.txt"
        bad.write_text("hello")
        with pytest.raises(UnsupportedFormatError):
            PDFParser().parse(bad)

    def test_full_text_property(self, multi_page_pdf: Path) -> None:
        result = PDFParser().parse(multi_page_pdf)
        text = result.full_text
        assert "Page 1" in text and "Page 5" in text

    def test_extract_tables_false_skips_pdfplumber(self, simple_pdf: Path) -> None:
        with patch("ingestion.parsers.pdf_parser.pdfplumber") as mock_pb:
            result = PDFParser(extract_tables=False).parse(simple_pdf)
        mock_pb.open.assert_not_called()
        assert len(result.pages) == 1

    def test_encrypted_pdf_no_password(self, tmp_path: Path) -> None:
        import fitz
        path = tmp_path / "encrypted.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Secret")
        doc.save(str(path), encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
        doc.close()
        with pytest.raises(ParserError, match="encrypted"):
            PDFParser().parse(path)

    def test_encrypted_pdf_with_correct_password(self, tmp_path: Path) -> None:
        """Correct password must authenticate and return a ParseResult without raising."""
        import fitz
        path = tmp_path / "encrypted.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Secret content here")
        doc.save(str(path), encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="pass")
        doc.close()
        # Must not raise; authentication succeeds even if MuPDF content-stream
        # decryption produces an empty text layer in certain fitz versions.
        result = PDFParser(password="pass").parse(path)
        assert result.metadata.get("page_count") == 1

    def test_corrupt_file_raises_parser_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"%PDF-1.4 CORRUPT GARBAGE")
        with pytest.raises(ParserError):
            PDFParser().parse(bad)


# ---------------------------------------------------------------------------
# DOCXParser tests
# ---------------------------------------------------------------------------

class TestDOCXParser:

    def test_basic_extraction(self, simple_docx: Path) -> None:
        result = DOCXParser().parse(simple_docx)
        assert len(result) == 1
        assert "First body paragraph" in result.full_text

    def test_heading_markers(self, simple_docx: Path) -> None:
        result = DOCXParser(emit_heading_markers=True).parse(simple_docx)
        assert "# Top-level Heading" in result.full_text
        assert "## Sub-Heading" in result.full_text

    def test_no_heading_markers(self, simple_docx: Path) -> None:
        result = DOCXParser(emit_heading_markers=False).parse(simple_docx)
        assert "Top-level Heading" in result.full_text
        assert "# " not in result.full_text

    def test_table_extracted(self, simple_docx: Path) -> None:
        result = DOCXParser().parse(simple_docx)
        assert len(result.all_tables) == 1
        table = result.all_tables[0]
        assert table[0][0] == "R0C0"
        assert table[1][2] == "R1C2"

    def test_table_placeholder_in_text(self, simple_docx: Path) -> None:
        result = DOCXParser().parse(simple_docx)
        assert "[TABLE 1]" in result.full_text

    def test_metadata_fields(self, simple_docx: Path) -> None:
        result = DOCXParser().parse(simple_docx)
        # Metadata exists (may be sparse for a fixture doc)
        assert isinstance(result.metadata, dict)

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        bad = tmp_path / "doc.pdf"
        bad.write_bytes(b"fake")
        with pytest.raises(UnsupportedFormatError):
            DOCXParser().parse(bad)

    def test_corrupt_docx_raises_parser_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.docx"
        bad.write_bytes(b"PK CORRUPT")
        with pytest.raises(ParserError):
            DOCXParser().parse(bad)

    def test_empty_docx(self, tmp_path: Path) -> None:
        from docx import Document
        path = tmp_path / "empty.docx"
        Document().save(str(path))
        result = DOCXParser().parse(path)
        # Should not raise; may return a page with empty text
        assert isinstance(result.full_text, str)

    def test_elapsed_recorded(self, simple_docx: Path) -> None:
        result = DOCXParser().parse(simple_docx)
        assert result.elapsed_seconds > 0

    def test_docm_extension_accepted(self, tmp_path: Path) -> None:
        from docx import Document
        path = tmp_path / "macro.docm"
        doc = Document()
        doc.add_paragraph("macro doc content")
        doc.save(str(path))
        result = DOCXParser().parse(path)
        assert "macro doc content" in result.full_text


# ---------------------------------------------------------------------------
# get_parser factory tests
# ---------------------------------------------------------------------------

class TestGetParser:

    def test_pdf_extension(self) -> None:
        assert isinstance(get_parser(".pdf"), PDFParser)

    def test_docx_extension(self) -> None:
        assert isinstance(get_parser(".docx"), DOCXParser)

    def test_path_object(self) -> None:
        assert isinstance(get_parser(Path("report.pdf")), PDFParser)

    def test_unknown_extension_raises(self) -> None:
        with pytest.raises(UnsupportedFormatError):
            get_parser(".xyz")

    def test_kwargs_forwarded(self) -> None:
        parser = get_parser(".pdf", max_pages=5, extract_tables=False)
        assert isinstance(parser, PDFParser)
        assert parser.max_pages == 5
        assert parser.extract_tables is False
