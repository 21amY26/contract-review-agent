from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import pytest

pytestmark = pytest.mark.integration

from ingestion.parsers.pdf_parser import PDFParser
from ingestion.parsers.docx_parser import DOCXParser
from ingestion.chunking.splitter import chunk_parse_result

_DATA_DIR = Path(__file__).resolve().parent / "data"


@pytest.fixture
def pdf_path() -> str:
    path = _DATA_DIR / "sample_report.pdf"
    if not path.exists():
        pytest.skip(f"sample PDF not found: {path}")
    return str(path)


@pytest.fixture
def docx_path() -> str:
    path = _DATA_DIR / "sample_report.docx"
    if not path.exists():
        pytest.skip(f"sample DOCX not found: {path}")
    return str(path)


def print_result(result):
    print("=" * 80)
    print("SOURCE:", result.source_path)

    print("\nMETADATA")
    print("-" * 80)
    for k, v in result.metadata.items():
        print(f"{k}: {v}")

    print("\nPAGES")
    print("-" * 80)

    for page in result.pages:
        print(f"\nPage {page.page_number}")
        print("Type:", page.page_type)

        print("\nTEXT")
        print(page.text[:1000])

        print("\nTABLE COUNT:", len(page.tables))

        for i, table in enumerate(page.tables, 1):
            print(f"\nTable {i}")
            for row in table:
                print(row)

        if page.warnings:
            print("\nWarnings:")
            for w in page.warnings:
                print("-", w)

    print("\nElapsed:", result.elapsed_seconds, "seconds")


def print_chunks(chunks):
    print("\n" + "=" * 80)
    print("GENERATED CHUNKS")
    print("=" * 80)

    print("Total Chunks:", len(chunks))

    for chunk in chunks:
        print("\n-------------------------------------")
        print("Chunk Index :", chunk.chunk_index)
        print("Heading     :", chunk.heading)
        print("Section ID  :", chunk.section_id)
        print("Pages       :", chunk.page_numbers)
        print("Split       :", chunk.is_split_fragment)

        print("\nText:")
        print(chunk.text[:500])

        if chunk.tables:
            print("\nTables:")
            for table in chunk.tables:
                for row in table:
                    print(row)


def test_pdf(pdf_path):
    print("\nTESTING PDF\n")

    parser = PDFParser(
        extract_tables=True
    )

    result = parser.parse(pdf_path)

    print_result(result)

    chunks = chunk_parse_result(
        result,
        source_name=Path(pdf_path).name
    )

    print_chunks(chunks)


def test_docx(docx_path):
    print("\nTESTING DOCX\n")

    parser = DOCXParser(
        include_headers_footers=True
    )

    result = parser.parse(docx_path)

    print_result(result)

    chunks = chunk_parse_result(
        result,
        source_name=Path(docx_path).name
    )

    print_chunks(chunks)


if __name__ == "__main__":

    # Change these paths
    pdf_file = "ingestion/parsers/tests/data/sample_report.pdf"
    docx_file = "ingestion/parsers/tests/data/sample_report.docx"

    if Path(pdf_file).exists():
        test_pdf(pdf_file)

    if Path(docx_file).exists():
        test_docx(docx_file)
