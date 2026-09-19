from pathlib import Path
import pytest
from ingestion.parsers import PDFParser
from ingestion.parsers._base import PageType

pytestmark = pytest.mark.integration


@pytest.fixture
def sample_pdf():
    pdf = Path(__file__).parent / "data" / "sample_report.pdf"
    if not pdf.exists():
        pytest.skip(f"Sample PDF not found: {pdf}")
    return pdf


def test_parse_real_pdf(sample_pdf):
    parser = PDFParser(extract_tables=True)
    result = parser.parse(sample_pdf)
    # Basic assertions
    assert result is not None
    assert len(result.pages) > 0
    assert result.elapsed_seconds >= 0
    assert isinstance(result.full_text, str)
    # Metadata should exist
    assert isinstance(result.metadata, dict)
    # Validate every page
    for page in result.pages:
        assert page.page_number >= 1
        assert page.page_type in (PageType.TEXT, PageType.SCAN)
        assert isinstance(page.text, str)
        assert isinstance(page.tables, list)
        assert isinstance(page.warnings, list)


def test_parser_returns_text_or_scan(sample_pdf):
    result = PDFParser().parse(sample_pdf)
    assert all(
        page.page_type in (PageType.TEXT, PageType.SCAN)
        for page in result.pages
    )


def test_parse_is_repeatable(sample_pdf):
    parser = PDFParser()
    first = parser.parse(sample_pdf)
    second = parser.parse(sample_pdf)
    assert first.full_text == second.full_text
    assert len(first.pages) == len(second.pages)
