"""Risk rule ingestion pipeline."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from src.ingestion.chroma_writer import add_records
from src.metadata.builders import build_risk_record
from src.vectordb.vectordb import get_risk_collection

logger = logging.getLogger(__name__)


def ingest_risks(path: str | Path) -> int:
    """Ingest a JSON risk rule file into the risk collection."""
    source_path = Path(path)
    rules = _load_rules(source_path)
    records = [build_risk_record(rule, index) for index, rule in enumerate(rules)]
    logger.info("prepared %d risk rule(s) from %s", len(records), source_path)
    inserted = add_records(get_risk_collection(), records)
    logger.info("risk ingestion complete: %d new rule(s)", inserted)
    return inserted


def _load_rules(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("risks"), list):
        data = data["risks"]
    if not isinstance(data, list):
        raise ValueError("risk_rules.json must contain a list or an object with a 'risks' list")

    rules: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"risk rule at index {index} is not an object")
        rules.append(item)
    return rules


def main() -> None:
    """CLI entry point for risk ingestion."""
    parser = argparse.ArgumentParser(description="Ingest risk rules into ChromaDB.")
    parser.add_argument("path", help="Path to risk_rules.json.")
    parser.add_argument("--log-level", default="INFO", help="Python logging level.")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s %(name)s: %(message)s")
    inserted = ingest_risks(args.path)
    print(f"Inserted {inserted} new risk rule(s).")


if __name__ == "__main__":
    main()

