"""Compliance and policy ingestion pipeline."""
from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable
from pathlib import Path

from ingestion.chunking.splitter import chunk_parse_result
from ingestion.parsers._base import PageResult, PageType, ParseResult

from src.ingestion.chroma_writer import add_records
from src.metadata.builders import build_compliance_record
from src.vectordb.vectordb import get_compliance_collection

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".md", ".txt"}


def ingest_compliance_file(path: str | Path, *, max_tokens: int = 500) -> int:
    """Ingest one markdown or text compliance document into Chroma."""
    source_path = Path(path)
    text = source_path.read_text(encoding="utf-8")
    parse_result = ParseResult(
        source_path=source_path,
        pages=[PageResult(page_number=1, text=text, page_type=PageType.TEXT)],
    )
    chunks = chunk_parse_result(parse_result, source_name=source_path.name, max_tokens=max_tokens)
    records = [build_compliance_record(source_path, chunk) for chunk in chunks if chunk.text.strip()]
    logger.info("prepared %d compliance chunk(s) from %s", len(records), source_path)
    return add_records(get_compliance_collection(), records)


def ingest_compliance(paths: Iterable[str | Path], *, max_tokens: int = 500) -> int:
    """Batch ingest compliance files or directories."""
    total = 0
    for path in _iter_compliance_files(paths):
        try:
            total += ingest_compliance_file(path, max_tokens=max_tokens)
        except Exception:
            logger.exception("failed to ingest compliance source %s", path)
    logger.info("compliance ingestion complete: %d new chunk(s)", total)
    return total


def _iter_compliance_files(paths: Iterable[str | Path]) -> Iterable[Path]:
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            for candidate in sorted(path.rglob("*")):
                if candidate.is_file() and candidate.suffix.lower() in _SUPPORTED_EXTENSIONS:
                    yield candidate
        elif path.is_file() and path.suffix.lower() in _SUPPORTED_EXTENSIONS:
            yield path
        else:
            logger.warning("skipping unsupported compliance path: %s", path)


def main() -> None:
    """CLI entry point for compliance ingestion."""
    parser = argparse.ArgumentParser(description="Ingest compliance documents into ChromaDB.")
    parser.add_argument("paths", nargs="+", help="Markdown/text files or directories.")
    parser.add_argument("--max-tokens", type=int, default=500, help="Chunk token target.")
    parser.add_argument("--log-level", default="INFO", help="Python logging level.")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s %(name)s: %(message)s")
    inserted = ingest_compliance(args.paths, max_tokens=args.max_tokens)
    print(f"Inserted {inserted} new compliance chunk(s).")


if __name__ == "__main__":
    main()

