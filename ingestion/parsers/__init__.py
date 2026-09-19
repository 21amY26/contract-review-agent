"""
ingestion.parsers
=================
Document parsing layer.  Import the parser you need directly:

    from ingestion.parsers import PDFParser, DOCXParser, OCRParser

Or use the registry helper to pick a parser by file extension:

    from ingestion.parsers import get_parser
    parser = get_parser(".pdf")
    result = parser.parse("report.pdf")
"""
from __future__ import annotations

from pathlib import Path

from ._base import (
    BaseParser,
    ExtractionWarning,
    PageResult,
    PageType,
    ParserError,
    ParseResult,
    UnsupportedFormatError,
)
from .docx_parser import DOCXParser
from .pdf_parser import PDFParser

__all__ = [
    # Parsers
    "PDFParser",
    "DOCXParser",
    # Base / types
    "BaseParser",
    "PageResult",
    "PageType",
    "ParseResult",
    # Exceptions
    "ParserError",
    "UnsupportedFormatError",
    "ExtractionWarning",
    # Factory
    "get_parser",
    "EXTENSION_MAP",
]

#: Maps lower-case file extension → default parser class.
EXTENSION_MAP: dict[str, type[BaseParser]] = {
    ".pdf":  PDFParser,
    ".docx": DOCXParser,
    ".docm": DOCXParser,
}


def get_parser(extension_or_path: str | Path, **kwargs) -> BaseParser:
    """
    Return an instantiated parser for the given file extension (or path).

    Parameters
    ----------
    extension_or_path:
        Either a file extension like ``".pdf"`` or a full path whose
        suffix is used.
    **kwargs:
        Forwarded to the parser constructor.

    Raises
    ------
    UnsupportedFormatError
        If no parser is registered for the extension.
    """
    s = str(extension_or_path)
    # Handle bare extension strings like ".pdf" or "pdf"
    # (Path(".pdf").suffix returns "" because it's treated as a hidden file)
    if s.startswith(".") and "/" not in s and "\\" not in s:
        suffix = s.lower()
    else:
        suffix = Path(s).suffix.lower()
    cls = EXTENSION_MAP.get(suffix)
    if cls is None:
        raise UnsupportedFormatError(
            f"No parser registered for '{suffix}'. "
            f"Supported: {sorted(EXTENSION_MAP)}"
        )
    return cls(**kwargs)
