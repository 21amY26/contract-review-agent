"""Citation-aware semantic retrieval over the Week-1 KB collections."""
from __future__ import annotations

import argparse
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

from src.embeddings.embedder import embed_texts
from src.vectordb.vectordb import (
    get_compliance_collection,
    get_contract_collection,
    get_risk_collection,
)


def search_contracts(query: str, n_results: int = 5) -> list[dict[str, Any]]:
    """Search the contract collection and return citation-aware results."""
    return _search(get_contract_collection(), query, n_results)


def search_compliance(query: str, n_results: int = 5) -> list[dict[str, Any]]:
    """Search the compliance collection and return citation-aware results."""
    return _search(get_compliance_collection(), query, n_results)


def search_risks(query: str, n_results: int = 5) -> list[dict[str, Any]]:
    """Search the risk collection and return citation-aware results."""
    return _search(get_risk_collection(), query, n_results)


def _search(collection: Any, query: str, n_results: int) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return []

    # An empty collection (KB not built yet) must degrade gracefully rather than
    # crash the agent that called us. Clamp n_results to what exists.
    try:
        available = collection.count()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not count collection, assuming empty: %s", exc)
        return []
    if available == 0:
        logger.warning(
            "Retrieval requested but the collection is empty — run ./build_kb.sh "
            "to populate the knowledge base. Returning no context."
        )
        return []

    query_embedding = embed_texts([query])[0]
    try:
        raw = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, available),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Collection query failed: %s", exc)
        return []
    documents = raw.get("documents", [[]])[0]
    metadatas = raw.get("metadatas", [[]])[0]
    distances = raw.get("distances", [[]])[0]

    results: list[dict[str, Any]] = []
    for text, metadata, distance in zip(documents, metadatas, distances, strict=False):
        clean_metadata = dict(metadata or {})
        results.append(
            {
                "text": text,
                "metadata": clean_metadata,
                "score": _distance_to_score(float(distance)),
            }
        )
    return results


def _distance_to_score(distance: float) -> float:
    """Convert Chroma cosine distance into a bounded similarity score."""
    return max(0.0, min(1.0, 1.0 - distance))


def main() -> None:
    """CLI entry point for retrieval smoke tests."""
    parser = argparse.ArgumentParser(description="Search a KB collection.")
    parser.add_argument("collection", choices=["contracts", "compliance", "risk"])
    parser.add_argument("query")
    parser.add_argument("--n-results", type=int, default=5)
    args = parser.parse_args()

    if args.collection == "contracts":
        results = search_contracts(args.query, n_results=args.n_results)
    elif args.collection == "compliance":
        results = search_compliance(args.query, n_results=args.n_results)
    else:
        results = search_risks(args.query, n_results=args.n_results)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
