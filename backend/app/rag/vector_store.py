"""ChromaDB persistent vector store with per-collection isolation."""

import logging
from typing import Any

import chromadb

from app.core.config import settings
from app.rag.embeddings import LocalEmbeddings

logger = logging.getLogger(__name__)


def _sanitize_metadata(meta: dict) -> dict:
    """Sanitize metadata for ChromaDB: only str/int/float/bool values allowed."""
    result = {}
    for k, v in meta.items():
        if v is None:
            result[k] = ""
        elif isinstance(v, (str, int, float, bool)):
            result[k] = v
        else:
            result[k] = str(v)
    return result


class VectorStore:
    """ChromaDB persistent client with per-collection isolation."""

    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self._embeddings = LocalEmbeddings(settings.default_embedding_model)

    def get_or_create_collection(self, name: str):
        """Get an existing collection or create a new one with cosine distance."""
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    async def add_documents(
        self,
        collection_name: str,
        chunks: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> int:
        """Embed chunks and add them to the named collection.

        Returns the number of chunks added.
        """
        if not chunks:
            return 0

        collection = self.get_or_create_collection(collection_name)
        embeddings = await self._embeddings.embed_documents(chunks)
        sanitized_meta = [_sanitize_metadata(m) for m in metadatas]

        collection.upsert(
            documents=chunks,
            embeddings=embeddings,
            metadatas=sanitized_meta,
            ids=ids,
        )
        logger.info(
            "Added %d chunks to collection '%s'.", len(chunks), collection_name
        )
        return len(chunks)

    async def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search the collection for the top-K most similar chunks.

        Returns a list of dicts: [{content, metadata, score}, ...].
        Returns an empty list if the collection does not exist or has no items.
        """
        try:
            collection = self._client.get_collection(name=collection_name)
        except Exception:
            logger.debug("Collection '%s' not found — returning empty results.", collection_name)
            return []

        count = collection.count()
        if count == 0:
            return []

        query_embedding = await self._embeddings.embed_query(query)
        n_results = min(top_k, count)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        formatted: list[dict[str, Any]] = []
        if results.get("documents") and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            distances = results["distances"][0]
            for doc, meta, dist in zip(docs, metas, distances):
                # cosine distance: 0=identical; convert to similarity score 0-1
                score = round(1.0 - dist, 4)
                formatted.append({"content": doc, "metadata": meta, "score": score})

        return formatted

    def delete_collection(self, name: str) -> None:
        """Delete a collection entirely."""
        try:
            self._client.delete_collection(name=name)
            logger.info("Deleted collection '%s'.", name)
        except Exception as exc:
            logger.warning("Could not delete collection '%s': %s", name, exc)

    def list_collections(self) -> list[str]:
        """Return names of all existing collections."""
        return [c.name for c in self._client.list_collections()]
