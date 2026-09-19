"""Contract ingestion pipeline: parse, chunk, enrich, embed, and store."""
from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable
from pathlib import Path

from ingestion.chunking.splitter import chunk_parse_result
from ingestion.parsers.docx_parser import DOCXParser
from ingestion.parsers.pdf_parser import PDFParser

from src.ingestion.chroma_writer import add_records
from src.metadata.builders import KBRecord, build_contract_record
from src.vectordb.vectordb import get_contract_collection

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".docm"}


def ingest_contract_file(path: str | Path, *, max_tokens: int = 500) -> int:
    """Ingest one PDF, DOCX, or DOCM contract into the contracts collection."""
    source_path = Path(path)
    parser = _select_parser(source_path)
    parse_result = parser.parse(source_path)
    chunks = chunk_parse_result(parse_result, source_name=source_path.name, max_tokens=max_tokens)
    records = [build_contract_record(parse_result, chunk) for chunk in chunks if chunk.text.strip()]
    logger.info("prepared %d contract chunk(s) from %s", len(records), source_path)
    return add_records(get_contract_collection(), records)


def ingest_contracts(paths: Iterable[str | Path], *, max_tokens: int = 500) -> int:
    """Batch ingest files or directories containing supported contract files."""
    total = 0
    for path in _iter_contract_files(paths):
        try:
            total += ingest_contract_file(path, max_tokens=max_tokens)
        except Exception:
            logger.exception("failed to ingest contract %s", path)
    logger.info("contract ingestion complete: %d new chunk(s)", total)
    return total


def _select_parser(path: Path) -> PDFParser | DOCXParser:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return PDFParser()
    if suffix in {".docx", ".docm"}:
        return DOCXParser()
    raise ValueError(f"Unsupported contract format: {path}")


def _iter_contract_files(paths: Iterable[str | Path]) -> Iterable[Path]:
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            for candidate in sorted(path.rglob("*")):
                if candidate.is_file() and candidate.suffix.lower() in _SUPPORTED_EXTENSIONS:
                    yield candidate
        elif path.is_file() and path.suffix.lower() in _SUPPORTED_EXTENSIONS:
            yield path
        else:
            logger.warning("skipping unsupported contract path: %s", path)


def main() -> None:
    """CLI entry point for contract ingestion."""
    parser = argparse.ArgumentParser(description="Ingest contract documents into ChromaDB.")
    parser.add_argument("paths", nargs="+", help="Contract files or directories.")
    parser.add_argument("--max-tokens", type=int, default=500, help="Chunk token target.")
    parser.add_argument("--log-level", default="INFO", help="Python logging level.")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s %(name)s: %(message)s")
    inserted = ingest_contracts(args.paths, max_tokens=args.max_tokens)
    print(f"Inserted {inserted} new contract chunk(s).")


if __name__ == "__main__":
    main()

