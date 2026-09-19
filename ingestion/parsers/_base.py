"""
Shared types, exceptions, and base class for all ingestion parsers.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class ParserError(Exception):
    """Raised when a parser cannot produce any usable output."""


class UnsupportedFormatError(ParserError):
    """Raised when the file type is not supported by this parser."""


class ExtractionWarning(UserWarning):
    """Non-fatal issue encountered during extraction (partial result)."""


class PageType(str, Enum):
    TEXT   = "text"    # native text layer present
    SCAN   = "scan"    # raster image, no text layer → OCR required
    MIXED  = "mixed"   # some text, some images


@dataclass(slots=True)
class PageResult:
    """Extracted content for a single page / section."""
    page_number: int                   # 1-based
    text: str                          # normalised, stripped content
    page_type: PageType = PageType.TEXT
    tables: list[list[list[str]]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip() and not self.tables


@dataclass
class ParseResult:
    """Aggregate result returned by every parser."""
    source_path: Path
    pages: list[PageResult] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def full_text(self) -> str:
        """All page text joined with double newlines."""
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def all_tables(self) -> list[list[list[str]]]:
        """Flat list of every table across all pages."""
        return [t for p in self.pages for t in p.tables]

    def __len__(self) -> int:
        return len(self.pages)


# ---------------------------------------------------------------------------
# Base parser
# ---------------------------------------------------------------------------

class BaseParser(ABC):
    """
    Abstract base for all document parsers.

    Subclasses implement ``_parse()``; this base handles path validation,
    timing, and top-level exception normalisation.
    """

    #: File extensions this parser accepts (lower-case, with dot).
    SUPPORTED_EXTENSIONS: frozenset[str] = frozenset()

    def __init__(self, *, max_pages: int | None = None) -> None:
        self.max_pages = max_pages
        self._log = logging.getLogger(type(self).__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, path: str | Path) -> ParseResult:
        """
        Parse *path* and return a :class:`ParseResult`.

        Raises
        ------
        FileNotFoundError
            If *path* does not exist.
        UnsupportedFormatError
            If the file extension is not in ``SUPPORTED_EXTENSIONS``.
        ParserError
            On unrecoverable extraction failure.
        """
        p = Path(path)
        self._validate(p)

        t0 = time.perf_counter()
        result = self._parse(p)
        result.elapsed_seconds = time.perf_counter() - t0

        self._log.info(
            "parsed %s → %d page(s) in %.2fs",
            p.name, len(result), result.elapsed_seconds,
        )
        return result

    def iter_pages(self, path: str | Path) -> Iterator[PageResult]:
        """Yield pages one at a time (memory-friendly for large docs)."""
        yield from self.parse(path).pages

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate(self, p: Path) -> None:
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        if not p.is_file():
            raise ParserError(f"Not a regular file: {p}")
        suffix = p.suffix.lower()
        if self.SUPPORTED_EXTENSIONS and suffix not in self.SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(
                f"{type(self).__name__} does not support '{suffix}'. "
                f"Supported: {sorted(self.SUPPORTED_EXTENSIONS)}"
            )

    @abstractmethod
    def _parse(self, path: Path) -> ParseResult:
        """Subclass hook — path is guaranteed to exist and be valid."""
