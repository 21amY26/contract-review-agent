"""Persistent ChromaDB collections for the Week-1 knowledge base."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

_PERSIST_DIR = Path("kb/chroma")
_CLIENT: chromadb.PersistentClient | None = None


def get_client() -> chromadb.PersistentClient:
    """Return the process-wide persistent Chroma client."""
    global _CLIENT
    if _CLIENT is None:
        _PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        _CLIENT = chromadb.PersistentClient(path=str(_PERSIST_DIR))
    return _CLIENT


def _get_collection(name: str) -> Any:
    return get_client().get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def get_contract_collection() -> Any:
    """Return the contracts collection."""
    return _get_collection("contracts")


def get_compliance_collection() -> Any:
    """Return the compliance collection."""
    return _get_collection("compliance")


def get_risk_collection() -> Any:
    """Return the risk collection."""
    return _get_collection("risk")
