"""Sentence-transformers embedding singleton for the knowledge base."""
from __future__ import annotations

import logging
import threading

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_MODEL_NAME = "BAAI/bge-small-en-v1.5"


class Embedder:
    """Lazy singleton wrapper around the BGE small embedding model."""

    _instance: "Embedder | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "Embedder":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._model = None
        return cls._instance

    @property
    def model(self) -> SentenceTransformer:
        """Load and return the sentence-transformers model once."""
        if self._model is None:
            logger.info("loading embedding model %s", _MODEL_NAME)
            self._model = SentenceTransformer(_MODEL_NAME)
        return self._model

    def embed_texts(self, texts: list[str], *, batch_size: int = 32) -> list[list[float]]:
        """Return normalized embeddings for a batch of texts."""
        clean_texts = [text if text is not None else "" for text in texts]
        if not clean_texts:
            return []

        embeddings = self.model.encode(
            clean_texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts using the process-wide BGE singleton."""
    return Embedder().embed_texts(texts)

