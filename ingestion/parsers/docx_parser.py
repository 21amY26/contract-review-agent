"""
DOCX parser — python-docx for text, styles, and embedded tables.

Strategy
--------
1. Walk document body elements in document order (not separately through
   ``doc.paragraphs`` and ``doc.tables``) so mixed para/table content
   preserves reading order.
2. Detect headings by style name and emit them with Markdown-style ``#``
   markers so downstream consumers can reconstruct document structure.
3. Extract tables as ``list[list[str]]`` grids, merging vertically-merged
   cells downward (python-docx exposes them as ``None``).
4. Headers / footers are extracted as metadata, not body text.
5. All OOXML namespaces are abstracted behind helper functions — callers
   never see raw XML.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterator
from xml.etree.ElementTree import Element

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from ._base import (
    BaseParser,
    PageResult,
    PageType,
    ParserError,
    ParseResult,
)

logger = logging.getLogger(__name__)

# python-docx style names that map to heading levels 1-9.
_HEADING_RE = re.compile(r"^heading\s*(\d)$", re.IGNORECASE)

# Styles treated as list items when they have no explicit bullet character.
_LIST_STYLE_RE = re.compile(r"list\s*(bullet|number|paragraph)", re.IGNORECASE)


class DOCXParser(BaseParser):
    """
    Extract structured text and tables from ``.docx`` / ``.docm`` files.

    Parameters
    ----------
    max_pages:
        Not applicable to DOCX (no page concept); kept for interface
        consistency and ignored.
    include_headers_footers:
        If ``True``, include header/footer text in ``metadata``.
    emit_heading_markers:
        If ``True`` (default), prefix headings with ``# / ## / …``
        Markdown markers for structure-aware downstream consumers.
    """

    SUPPORTED_EXTENSIONS = frozenset({".docx", ".docm"})

    def __init__(
        self,
        *,
        max_pages: int | None = None,
        include_headers_footers: bool = False,
        emit_heading_markers: bool = True,
    ) -> None:
        super().__init__(max_pages=max_pages)
        self.include_headers_footers = include_headers_footers
        self.emit_heading_markers = emit_heading_markers

    # ------------------------------------------------------------------
    # Core implementation
    # ------------------------------------------------------------------

    def _parse(self, path: Path) -> ParseResult:
        result = ParseResult(source_path=path)

        try:
            doc = Document(str(path))
        except Exception as exc:
            raise ParserError(f"Cannot open DOCX '{path.name}': {exc}") from exc

        result.metadata = self._extract_metadata(doc, path)

        lines: list[str] = []
        tables: list[list[list[str]]] = []

        for block in self._iter_body_blocks(doc):
            if isinstance(block, Paragraph):
                rendered = self._render_paragraph(block)
                if rendered is not None:
                    lines.append(rendered)
            elif isinstance(block, Table):
                grid = self._extract_table(block)
                if grid:
                    tables.append(grid)
                    # Embed a plain-text placeholder so table position is
                    # preserved relative to surrounding paragraphs.
                    lines.append(f"[TABLE {len(tables)}]")

        full_text = "\n".join(lines).strip()

        # DOCX has no page concept — return as a single "page".
        result.pages.append(
            PageResult(
                page_number=1,
                text=full_text,
                page_type=PageType.TEXT,
                tables=tables,
            )
        )
        return result

    # ------------------------------------------------------------------
    # Body block iteration (preserves document order)
    # ------------------------------------------------------------------

    @staticmethod
    def _iter_body_blocks(doc: Document) -> Iterator[Paragraph | Table]:
        """
        Walk ``<w:body>`` children and yield ``Paragraph`` or ``Table``
        objects in document order.  This is the only reliable way to
        preserve mixed content ordering in python-docx.
        """
        body: Element = doc.element.body
        for child in body:
            tag = child.tag
            if tag == qn("w:p"):
                yield Paragraph(child, doc)
            elif tag == qn("w:tbl"):
                yield Table(child, doc)
            # w:sdt (content controls), w:sectPr, etc. are skipped intentionally.

    # ------------------------------------------------------------------
    # Paragraph rendering
    # ------------------------------------------------------------------

    def _render_paragraph(self, para: Paragraph) -> str | None:
        """Return a string representation of *para*, or ``None`` for blank."""
        text = para.text  # concatenates all runs
        if not text.strip():
            return None

        style_name: str = (para.style.name or "").strip()

        # Heading detection
        m = _HEADING_RE.match(style_name)
        if m and self.emit_heading_markers:
            level = int(m.group(1))
            prefix = "#" * level
            return f"{prefix} {text.strip()}"

        # List item detection (best-effort; numbering XML is complex)
        if _LIST_STYLE_RE.search(style_name):
            return f"- {text.strip()}"

        return text.strip()

    # ------------------------------------------------------------------
    # Table extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_table(table: Table) -> list[list[str]]:
        """
        Return the table as a 2-D list of strings.

        Vertically-merged cells (``<w:vMerge/>`` continuations) are
        filled with the value of the cell above them so every row has
        the same width.
        """
        grid: list[list[str]] = []
        prev_row: list[str] = []

        for row in table.rows:
            current: list[str] = []
            for col_idx, cell in enumerate(row.cells):
                cell_text = _cell_text(cell)
                # Detect vertical merge continuation: same object as prev row
                if (
                    grid
                    and col_idx < len(prev_row)
                    and cell_text == ""
                    and _is_vmerge_continuation(cell)
                ):
                    current.append(prev_row[col_idx])
                else:
                    current.append(cell_text)
            grid.append(current)
            prev_row = current

        return grid

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _extract_metadata(self, doc: Document, path: Path) -> dict:
        core = doc.core_properties
        meta: dict = {
            "title":    core.title or "",
            "author":   core.author or "",
            "subject":  core.subject or "",
            "keywords": core.keywords or "",
            "created":  str(core.created or ""),
            "modified": str(core.modified or ""),
            "revision": core.revision or 0,
        }
        meta = {k: v for k, v in meta.items() if v not in ("", 0, "None")}

        if self.include_headers_footers:
            meta["headers"] = list(_iter_section_text(doc, "header"))
            meta["footers"] = list(_iter_section_text(doc, "footer"))

        return meta


# ---------------------------------------------------------------------------
# OOXML helpers
# ---------------------------------------------------------------------------

def _cell_text(cell: _Cell) -> str:
    """Return stripped, newline-joined text from all paragraphs in a cell."""
    parts = [p.text.strip() for p in cell.paragraphs if p.text.strip()]
    return "\n".join(parts)


def _is_vmerge_continuation(cell: _Cell) -> bool:
    """
    Return ``True`` if this cell is a vertical-merge continuation
    (i.e., it carries ``<w:vMerge/>`` with no ``val`` attribute, meaning
    it repeats the cell above).
    """
    tc = cell._tc  # type: ignore[attr-defined]
    vmerge = tc.find(qn("w:tcPr") + "/" + qn("w:vMerge"))
    if vmerge is None:
        # Also check directly under tc
        for pr in tc.findall(qn("w:tcPr")):
            vm = pr.find(qn("w:vMerge"))
            if vm is not None:
                # No val attribute = continuation; val="restart" = first cell
                return vm.get(qn("w:val")) is None
    return False


def _iter_section_text(doc: Document, kind: str) -> Iterator[str]:
    """Yield non-empty text from all header or footer sections."""
    for section in doc.sections:
        obj = getattr(section, f"{kind}", None)
        if obj is None:
            continue
        text = "\n".join(
            p.text.strip() for p in obj.paragraphs if p.text.strip()
        )
        if text:
            yield text
