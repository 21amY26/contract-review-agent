"""
PDF parser — PyMuPDF (fitz) for text/metadata, pdfplumber for tables.

Strategy
--------
1. Open with PyMuPDF for speed and metadata.
2. On each page, check whether a native text layer is present:
   - If yes  → extract text via ``page.get_text("text")``.
3. For table-heavy pages, delegate to pdfplumber for structured extraction.
4. Partial failures per-page are recorded as warnings, not exceptions —
   the caller gets as much content as possible.
"""
from __future__ import annotations

import logging
import re
import warnings
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import pdfplumber

from ._base import (
    BaseParser,
    ExtractionWarning,
    PageResult,
    PageType,
    ParserError,
    ParseResult,
)

logger = logging.getLogger(__name__)

# Minimum character count on a page to consider the text layer non-empty.
_MIN_TEXT_CHARS = 20

# pdfplumber table settings — tighter snap tolerance for cleaner output.
_TABLE_SETTINGS: dict[str, Any] = {
    "vertical_strategy":   "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance":      3,
    "join_tolerance":      3,
    "edge_min_length":     10,
}


class PDFParser(BaseParser):
    """
    Extract text, metadata, and tables from PDF files.

    Parameters
    ----------
    max_pages:
        Hard cap on pages processed. ``None`` means no limit.
    extract_tables:
        If ``True`` (default), run pdfplumber on every page for table
        detection. Set to ``False`` for faster extraction when tables
        are not needed.
    password:
        Password for encrypted PDFs.
    """

    SUPPORTED_EXTENSIONS = frozenset({".pdf"})

    def __init__(
        self,
        *,
        max_pages: int | None = None,
        extract_tables: bool = True,
        password: str | None = None,
    ) -> None:
        super().__init__(max_pages=max_pages)
        self.extract_tables = extract_tables
        self.password = password

    # ------------------------------------------------------------------
    # Core implementation
    # ------------------------------------------------------------------

    def _parse(self, path: Path) -> ParseResult:
        result = ParseResult(source_path=path)

        try:
            fitz_doc = fitz.open(str(path))
        except Exception as exc:
            raise ParserError(f"Cannot open PDF '{path.name}': {exc}") from exc

        try:
            if fitz_doc.needs_pass:
                if not self.password:
                    raise ParserError(
                        f"PDF '{path.name}' is encrypted and no password was provided."
                    )
                ok = fitz_doc.authenticate(self.password)
                if not ok:
                    raise ParserError(f"Wrong password for '{path.name}'.")

            result.metadata = self._extract_metadata(fitz_doc)
            total_pages = fitz_doc.page_count
            limit = min(total_pages, self.max_pages) if self.max_pages else total_pages

            if self.extract_tables:
                plumber_doc = self._open_plumber(path)
            else:
                plumber_doc = None

            try:
                for page_index in range(limit):
                    page_result = self._parse_page(
                        fitz_doc=fitz_doc,
                        plumber_doc=plumber_doc,
                        page_index=page_index,
                    )
                    result.pages.append(page_result)
                    if page_result.warnings:
                        result.warnings.extend(page_result.warnings)
            finally:
                if plumber_doc is not None:
                    plumber_doc.close()

            if limit < total_pages:
                result.warnings.append(
                    f"Only {limit} of {total_pages} pages were processed (max_pages={self.max_pages})."
                )

        finally:
            fitz_doc.close()

        return result

    # ------------------------------------------------------------------
    # Per-page extraction
    # ------------------------------------------------------------------

    def _parse_page(
        self,
        fitz_doc: fitz.Document,
        plumber_doc: pdfplumber.PDF | None,
        page_index: int,
    ) -> PageResult:
        page_number = page_index + 1
        page_warnings: list[str] = []

        # --- Text extraction via PyMuPDF ---
        fitz_page: fitz.Page = fitz_doc[page_index]
        raw_text = ""
        page_type = PageType.TEXT

        try:
            raw_text = fitz_page.get_text("text")  # type: ignore[attr-defined]
            if len(raw_text.strip()) < _MIN_TEXT_CHARS:
                # Check whether there are images (scan candidate)
                if fitz_page.get_images(full=False):
                    page_type = PageType.SCAN
                    page_warnings.append(
                        f"Page {page_number}: no readable text layer detected — "
                    )
                    warnings.warn(page_warnings[-1], ExtractionWarning, stacklevel=3)
                else:
                    page_type = PageType.TEXT  # Genuinely blank page
        except Exception as exc:
            page_warnings.append(f"Page {page_number}: fitz text extraction failed: {exc}")
            self._log.warning("Page %d fitz error: %s", page_number, exc)

        text = _normalise_text(raw_text)

        # --- Table extraction via pdfplumber ---
        tables: list[list[list[str]]] = []
        if self.extract_tables and plumber_doc is not None and page_type != PageType.SCAN:
            try:
                pl_page = plumber_doc.pages[page_index]
                raw_tables = pl_page.extract_tables(_TABLE_SETTINGS) or []
                tables = [_clean_table(t) for t in raw_tables if t]
            except Exception as exc:
                page_warnings.append(f"Page {page_number}: table extraction failed: {exc}")
                self._log.debug("Page %d pdfplumber error: %s", page_number, exc)

        return PageResult(
            page_number=page_number,
            text=text,
            page_type=page_type,
            tables=tables,
            warnings=page_warnings,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _open_plumber(path: Path) -> pdfplumber.PDF | None:
        try:
            return pdfplumber.open(str(path))
        except Exception as exc:
            logger.warning("pdfplumber failed to open '%s': %s — tables disabled.", path.name, exc)
            return None

    @staticmethod
    def _extract_metadata(doc: fitz.Document) -> dict:
        raw: dict = doc.metadata or {}
        meta: dict = {k: v for k, v in raw.items() if v}
        meta["page_count"] = doc.page_count
        meta["is_encrypted"] = doc.needs_pass
        return meta


# ---------------------------------------------------------------------------
# Text / table normalisation utilities
# ---------------------------------------------------------------------------

_MULTI_BLANK = re.compile(r"\n{3,}")
_TRAILING_WS = re.compile(r"[ \t]+\n")


def _normalise_text(text: str) -> str:
    """Strip trailing whitespace from lines; collapse 3+ blank lines into 2."""
    text = _TRAILING_WS.sub("\n", text)
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def _clean_table(raw: list[list[str | None]]) -> list[list[str]]:
    """Replace None cells with empty strings; strip whitespace."""
    return [
        [("" if cell is None else str(cell).strip()) for cell in row]
        for row in raw
    ]
