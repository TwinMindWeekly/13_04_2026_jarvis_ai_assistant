"""Build a document similarity graph from ChromaDB embeddings.

Algorithm:
  1. Load the documents metadata index (filename, size, folder, …).
  2. For each document, fetch all its chunk embeddings from ChromaDB
     (filter on ``metadata.doc_id``).
  3. Compute the document-level embedding as the mean of its chunks.
  4. Compute the pairwise cosine similarity matrix.
  5. Emit an edge for every pair whose similarity exceeds the threshold.

Complexity is O(n²) which is fine up to ~1 000 documents. Beyond that we
should switch to ChromaDB's HNSW nearest-neighbour queries (top-K per
document) which is O(n·k·log n).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.models.graph_schemas import (
    GraphData,
    GraphLink,
    GraphMeta,
    GraphNode,
    GraphStats,
)

logger = logging.getLogger(__name__)

_DEFAULT_COLLECTION = "jarvis_default"
_METADATA_FILENAME = "documents_metadata.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_documents_index() -> list[dict]:
    """Read the documents metadata index produced by the documents router."""
    path = Path(settings.upload_dir) / _METADATA_FILENAME
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception as exc:
        logger.warning("Could not read documents metadata index: %s", exc)
        return []


def _folder_of(filename: str) -> str:
    """Return the parent folder name for color grouping. Empty if none."""
    parent = Path(filename).parent
    return "" if str(parent) in ("", ".") else str(parent)


def _cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    """Pairwise cosine similarity — normalized dot product."""
    if vectors.size == 0:
        return np.array([])
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    # Avoid divide-by-zero for accidental zero vectors.
    norms[norms == 0] = 1.0
    normalized = vectors / norms
    return normalized @ normalized.T


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


async def build_document_graph(threshold: float = 0.5) -> GraphData:
    """Compute the document similarity graph from current ChromaDB state.

    Args:
        threshold: Minimum cosine similarity for an edge to be emitted.
            Default 0.5 keeps the graph readable while still revealing
            meaningful clusters.

    Returns:
        GraphData with nodes, links and metadata. Returns a graph with just
        nodes (no links) when fewer than two documents are indexed.
    """
    docs = _load_documents_index()
    nodes: list[GraphNode] = []
    for doc in docs:
        filename = doc.get("filename", "")
        nodes.append(
            GraphNode(
                id=doc.get("id", ""),
                label=filename,
                folder=_folder_of(filename),
                chunks_count=int(doc.get("chunks_count", 0)),
                size_bytes=int(doc.get("size_bytes", 0)),
                uploaded_at=doc.get("uploaded_at", ""),
                file_ext=Path(filename).suffix.lower(),
            )
        )

    if len(nodes) < 2:
        logger.info("Graph build skipped — need 2+ documents, got %d", len(nodes))
        return GraphData(
            nodes=nodes,
            links=[],
            meta=GraphMeta(
                total_docs=len(nodes),
                total_links=0,
                threshold=threshold,
                generated_at=datetime.now(timezone.utc).isoformat(),
                cached=False,
            ),
        )

    # Fetch all chunks with embeddings once (single round-trip to ChromaDB).
    # Lazy import so test suites without chromadb can still import this module.
    import chromadb  # noqa: PLC0415

    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    try:
        collection = client.get_collection(name=_DEFAULT_COLLECTION)
    except Exception:
        logger.info("Collection '%s' not found — empty graph.", _DEFAULT_COLLECTION)
        return GraphData(
            nodes=nodes,
            links=[],
            meta=GraphMeta(
                total_docs=len(nodes),
                total_links=0,
                threshold=threshold,
                generated_at=datetime.now(timezone.utc).isoformat(),
                cached=False,
            ),
        )

    result = collection.get(include=["embeddings", "metadatas"])
    all_embeds: list[list[float]] = result.get("embeddings") or []
    all_metas: list[dict] = result.get("metadatas") or []

    # Group chunk embeddings by doc_id.
    per_doc: dict[str, list[list[float]]] = {}
    for emb, meta in zip(all_embeds, all_metas):
        doc_id = meta.get("doc_id") if meta else None
        if not doc_id:
            continue
        per_doc.setdefault(doc_id, []).append(emb)

    # Keep only the documents that actually have chunks.
    doc_ids: list[str] = [n.id for n in nodes if n.id in per_doc]
    if len(doc_ids) < 2:
        logger.info("Graph build — fewer than 2 documents have embeddings.")
        return GraphData(
            nodes=nodes,
            links=[],
            meta=GraphMeta(
                total_docs=len(nodes),
                total_links=0,
                threshold=threshold,
                generated_at=datetime.now(timezone.utc).isoformat(),
                cached=False,
            ),
        )

    # Mean-pool each doc's chunk embeddings.
    doc_vectors = np.array(
        [np.mean(np.array(per_doc[d]), axis=0) for d in doc_ids],
        dtype=np.float32,
    )

    similarity = _cosine_similarity_matrix(doc_vectors)

    # Emit edges above threshold (upper triangle only — graph is undirected).
    links: list[GraphLink] = []
    n = len(doc_ids)
    for i in range(n):
        for j in range(i + 1, n):
            weight = float(similarity[i][j])
            if weight >= threshold:
                links.append(
                    GraphLink(
                        source=doc_ids[i],
                        target=doc_ids[j],
                        weight=round(weight, 4),
                    )
                )

    logger.info(
        "Graph built — %d nodes, %d links (threshold=%.2f)",
        len(nodes),
        len(links),
        threshold,
    )

    return GraphData(
        nodes=nodes,
        links=links,
        meta=GraphMeta(
            total_docs=len(nodes),
            total_links=len(links),
            threshold=threshold,
            generated_at=datetime.now(timezone.utc).isoformat(),
            cached=False,
        ),
    )


# ---------------------------------------------------------------------------
# Stats (cheap — no similarity computation)
# ---------------------------------------------------------------------------


def get_graph_stats() -> GraphStats:
    """Return counts without computing the full similarity graph."""
    docs = _load_documents_index()
    total_chunks = sum(int(d.get("chunks_count", 0)) for d in docs)

    cache_path = Path(settings.chroma_persist_dir) / "graph_cache.json"
    return GraphStats(
        total_docs=len(docs),
        total_chunks=total_chunks,
        cache_exists=cache_path.exists(),
    )
