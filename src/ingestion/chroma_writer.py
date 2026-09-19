"""Duplicate-safe Chroma insertion helpers."""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from src.embeddings.embedder import embed_texts
from src.metadata.builders import KBRecord

logger = logging.getLogger(__name__)


def add_records(
    collection: Any,
    records: Iterable[KBRecord],
    *,
    batch_size: int = 64,
) -> int:
    """Embed and add records to Chroma, skipping records with existing IDs."""
    pending = list(records)
    inserted = 0

    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        new_records = _filter_new_records(collection, batch)
        if not new_records:
            continue

        documents = [record.text for record in new_records]
        embeddings = embed_texts(documents)
        collection.add(
            ids=[record.id for record in new_records],
            documents=documents,
            metadatas=[record.metadata for record in new_records],
            embeddings=embeddings,
        )
        inserted += len(new_records)
        logger.info("inserted %d record(s) into %s", len(new_records), collection.name)

    skipped = len(pending) - inserted
    if skipped:
        logger.info("skipped %d duplicate record(s) in %s", skipped, collection.name)
    return inserted


def _filter_new_records(collection: Any, records: list[KBRecord]) -> list[KBRecord]:
    ids = [record.id for record in records]
    existing = _existing_ids(collection, ids)
    return [record for record in records if record.id not in existing]


def _existing_ids(collection: Any, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    try:
        result = collection.get(ids=ids, include=[])
    except TypeError:
        result = collection.get(ids=ids)
    return set(result.get("ids", []))
