"""Local sentence-transformers embeddings — free, no API key required."""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LocalEmbeddings:
    """sentence-transformers local embeddings — free, no API key.

    Uses a singleton model instance to avoid loading the model multiple times
    (it's a heavy ~90 MB download on first use).
    """

    _instance: Optional[object] = None  # singleton SentenceTransformer model

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model_name = model_name

    def _get_model(self):
        """Lazy-load and cache the SentenceTransformer model as a singleton."""
        if LocalEmbeddings._instance is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading SentenceTransformer model: %s", self.model_name)
            LocalEmbeddings._instance = SentenceTransformer(self.model_name)
            logger.info("SentenceTransformer model loaded successfully.")
        return LocalEmbeddings._instance

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous embedding — runs in a thread via asyncio.to_thread."""
        model = self._get_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents asynchronously.

        Runs the sync SentenceTransformer encode in a thread pool to avoid
        blocking the event loop.
        """
        if not texts:
            return []
        return await asyncio.to_thread(self._embed_sync, texts)

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string asynchronously."""
        results = await self.embed_documents([text])
        return results[0]
