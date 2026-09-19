"""
test_real_docx.py
------------------
Integration test for DOCXParser against a real .docx file.

Marked as 'integration' so it does NOT run automatically with the unit
test suite (test_parsers.py) or in CI unless explicitly requested.

Run manually:
    pytest ingestion/parsers/tests/test_real_docx.py -v -m integration

Or as a standalone script:
    python ingestion/parsers/tests/test_real_docx.py
    python ingestion/parsers/tests/test_real_docx.py path/to/your/file.docx
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make project root importable when run directly (not via pytest from root)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ingestion.parsers import DOCXParser
from ingestion.parsers._base import ParserError

# Default sample file lives alongside this test
_SAMPLE_DOCX = Path(__file__).parent / "data" / "sample_report.docx"


# ---------------------------------------------------------------------------
# Pytest integration test
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_real_docx_parses_successfully() -> None:
    """Smoke test: a real-world-shaped .docx parses without errors."""
    assert _SAMPLE_DOCX.exists(), f"Sample file missing: {_SAMPLE_DOCX}"

    result = DOCXParser().parse(_SAMPLE_DOCX)

    # Headings extracted with markers
    assert "# Quarterly Financial Report Q3 2024" in result.full_text
    assert "## Executive Summary" in result.full_text
    assert "## Regional Breakdown" in result.full_text

    # Body paragraph content present
    assert "12% increase" in result.full_text

    # Bullet list rendered
    assert "- Product revenue: 2.8M (up 15%)" in result.full_text

    # Table extracted correctly
    assert len(result.all_tables) == 1
    table = result.all_tables[0]
    assert table[0] == ["Region", "Revenue", "YoY Growth"]
    assert table[1] == ["North America", "2.43M", "12%"]

    # No fatal warnings expected on a clean file
    assert result.elapsed_seconds > 0


# ---------------------------------------------------------------------------
# Standalone script mode — run with: python test_real_docx.py [file.docx]
# ---------------------------------------------------------------------------

def _run_as_script() -> None:
    docx_path = sys.argv[1] if len(sys.argv) > 1 else str(_SAMPLE_DOCX)

    print("=" * 60)
    print(f"  FILE : {docx_path}")
    print("=" * 60)

    try:
        result = DOCXParser().parse(docx_path)
    except FileNotFoundError:
        print(f"\n❌  File not found: {docx_path}")
        sys.exit(1)
    except ParserError as e:
        print(f"\n❌  Parse error: {e}")
        sys.exit(1)

    print("\n📋  METADATA")
    print("-" * 40)
    for k, v in result.metadata.items():
        print(f"  {k:<20} {v}")

    print("\n📄  SUMMARY")
    print("-" * 40)
    print(f"  Elapsed          : {result.elapsed_seconds:.3f}s")
    print(f"  Total characters : {len(result.full_text):,}")
    print(f"  Total tables     : {len(result.all_tables)}")
    if result.warnings:
        print(f"\n⚠️   WARNINGS ({len(result.warnings)})")
        for w in result.warnings:
            print(f"  • {w}")

    if result.all_tables:
        print(f"\n📊  TABLES")
        print("-" * 40)
        for i, table in enumerate(result.all_tables, 1):
            print(f"\n  Table {i}  ({len(table)} rows × {len(table[0])} cols)")
            for row in table:
                print("  | " + " | ".join(f"{cell:<15}" for cell in row) + " |")

    print(f"\n📃  FULL TEXT")
    print("-" * 40)
    print(result.full_text)

    print("\n" + "=" * 60)
    print("  ✅  Parse complete")
    print("=" * 60)


if __name__ == "__main__":
    _run_as_script()
