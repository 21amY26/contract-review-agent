"""
ingestion/chunking/splitter.py

Two-stage, contract-aware chunker.

Stage 1 (structural):
    Split page text into clause-level blocks using:
      - Markdown heading markers ("#", "##", ...) — emitted by DOCXParser
      - Legal numbering patterns ("8.2", "Section 9", "Article IV", "(a)")
        — the only signal available for PDFParser output, since PyMuPDF's
        get_text("text") carries no font/bold metadata.

Stage 2 (fallback):
    Any block still too large gets recursively split with overlap, using
    LangChain's RecursiveCharacterTextSplitter. Most clauses won't need
    this; long indemnification/liability clauses usually will.

Input:  ingestion.parsers._base.ParseResult (what PDFParser/DOCXParser return)
Output: list[Chunk]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ingestion.parsers._base import ParseResult, PageResult, PageType

# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    text: str
    section_id: str | None = None              # e.g. "8.2"
    heading: str | None = None                  # e.g. "Indemnification"
    page_numbers: list[int] = field(default_factory=list)   # meaningful for PDF only
    tables: list[list[list[str]]] = field(default_factory=list)
    source: str = ""
    chunk_index: int = 0
    is_split_fragment: bool = False             # True if this came from stage-2 fallback


# ---------------------------------------------------------------------------
# Stage 1 — structural boundary detection
# ---------------------------------------------------------------------------

# DOCXParser-emitted markdown headings: "# Title", "## Sub", etc.
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

# Legal numbering at line start: "8.2 Indemnification", "Section 9", "Article IV",
# "(a) ...". Conservative on purpose — false negatives (missed boundary) are
# safer than false positives (splitting mid-sentence on a stray "3.1%").
_CLAUSE_RE = re.compile(
    r"""^(
        (?:ARTICLE|Article|SECTION|Section)\s+[\dIVXLC]+\b
        |
        \d{1,2}(?:\.\d{1,2}){0,3}\.?(?=\s+[A-Z(])
        |
        \([a-zA-Z]{1,3}\)(?=\s+[A-Z])
    )""",
    re.VERBOSE,
)

_TABLE_PLACEHOLDER_RE = re.compile(r"^\[TABLE (\d+)\]$")


@dataclass
class _Block:
    section_id: str | None
    heading: str | None
    text: str
    table_refs: list[int]  # indices into page.tables, 0-based


def _split_into_blocks(text: str) -> list[_Block]:
    """Split one page's text into clause-level blocks, in document order."""
    lines = text.split("\n")
    blocks: list[_Block] = []
    cur_id, cur_heading, cur_lines, cur_tables = None, None, [], []

    def flush():
        if cur_lines:
            blocks.append(_Block(cur_id, cur_heading, "\n".join(cur_lines).strip(), cur_tables[:]))

    for line in lines:
        stripped = line.strip()

        tbl_match = _TABLE_PLACEHOLDER_RE.match(stripped)
        if tbl_match:
            cur_tables.append(int(tbl_match.group(1)) - 1)
            cur_lines.append(line)
            continue

        md = _MD_HEADING_RE.match(line)
        clause = _CLAUSE_RE.match(stripped) if not md else None

        if md:
            flush()
            cur_id, cur_heading, cur_lines, cur_tables = None, md.group(2).strip(), [line], []
        elif clause and len(stripped) < 200:
            flush()
            cur_id = clause.group(0).strip().rstrip(".")
            cur_heading = stripped
            cur_lines, cur_tables = [line], []
        else:
            cur_lines.append(line)

    flush()
    return blocks


# ---------------------------------------------------------------------------
# Stage 2 — token-bounded fallback split with overlap
# ---------------------------------------------------------------------------

def _recursive_split(text: str, chunk_size: int, overlap: int,
                      separators: list[str] | None = None) -> list[str]:
    """
    Minimal stand-in for langchain's RecursiveCharacterTextSplitter.
    Tries separators in order (paragraph -> line -> sentence -> word -> char),
    recursing into oversized pieces, then stitches results back together
    with character-based overlap.
    """
    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    sep = separators[0]
    rest = separators[1:]

    if sep == "":
        # Last resort: hard character split.
        pieces = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    else:
        parts = text.split(sep)
        pieces = []
        for part in parts:
            if len(part) <= chunk_size:
                if part.strip():
                    pieces.append(part)
            elif rest:
                pieces.extend(_recursive_split(part, chunk_size, overlap, rest))
            else:
                pieces.append(part)

    # Merge small adjacent pieces up to chunk_size, with overlap carried forward.
    merged: list[str] = []
    buf = ""
    for piece in pieces:
        candidate = (buf + sep + piece) if buf else piece
        if len(candidate) <= chunk_size:
            buf = candidate
        else:
            if buf:
                merged.append(buf)
            buf = piece
    if buf:
        merged.append(buf)

    # Apply overlap: prepend tail of previous chunk to the next one.
    if overlap > 0 and len(merged) > 1:
        overlapped = [merged[0]]
        for i in range(1, len(merged)):
            tail = merged[i - 1][-overlap:]
            overlapped.append(tail + merged[i])
        return overlapped

    return merged


_fallback_splitter = None  # kept as a no-op placeholder; see _maybe_split_block


def _approx_tokens(text: str) -> int:
    # swap for a real tokenizer (tiktoken / your embedding model's tokenizer)
    # if you need precision; this is good enough to decide "split or not".
    return len(text) // 4


def _maybe_split_block(block: _Block, max_tokens: int) -> list[str]:
    if _approx_tokens(block.text) <= max_tokens:
        return [block.text]
    return _recursive_split(block.text, chunk_size=1800, overlap=250)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def chunk_parse_result(
    result: ParseResult,
    source_name: str,
    max_tokens: int = 500,
) -> list[Chunk]:
    """
    Convert a ParseResult (from PDFParser or DOCXParser) into clause-level
    Chunks, prefixing each chunk's text with its heading/section_id so
    embeddings see structural context even without separate metadata lookup.
    """
    chunks: list[Chunk] = []
    idx = 0

    for page in result.pages:  # 1 page for DOCX, N pages for PDF
        for block in _split_into_blocks(page.text):
            prefix = ""
            if block.heading:
                prefix = f"{block.heading}\n"

            fragments = _maybe_split_block(block, max_tokens)
            for frag_i, frag in enumerate(fragments):
                body = frag if frag_i == 0 else frag  # prefix only matters for retrieval framing
                chunk_text = (prefix + body) if frag_i == 0 else body

                tables = (
                    [page.tables[i] for i in block.table_refs if i < len(page.tables)]
                    if frag_i == 0 else []
                )

                chunks.append(
                    Chunk(
                        text=chunk_text,
                        section_id=block.section_id,
                        heading=block.heading,
                        page_numbers=[page.page_number] if page.page_type != PageType.SCAN else [],
                        tables=tables,
                        source=source_name,
                        chunk_index=idx,
                        is_split_fragment=len(fragments) > 1,
                    )
                )
                idx += 1

    return chunks
