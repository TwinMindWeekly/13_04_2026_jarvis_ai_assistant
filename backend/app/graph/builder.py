"""Build a document knowledge graph from [[wikilinks]] in vault Markdown files.

Algorithm (Phase 10 — wikilinks only, no cosine similarity):
  1. Load the documents metadata index (filename, size, wikilinks, …).
  2. For each document that has wikilinks, resolve [[target]] names to
     document IDs via fuzzy filename matching.
  3. Emit an edge for every resolved wikilink.
  4. Build a backlinks index (reverse lookup: who links to this doc?).

This is O(n·k) where k = average wikilinks per doc — much cheaper than
the O(n²) cosine similarity matrix used in Phase 8.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.models.graph_schemas import (
    GraphData,
    GraphLink,
    GraphMeta,
    GraphNode,
    GraphStats,
)

logger = logging.getLogger(__name__)

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


def _folder_of(doc: dict) -> str:
    """Return folder_path from document metadata for color grouping.

    Priority:
      1. Explicit `folder_path` field (new in Part B)
      2. Legacy: parse parent from filename (for old metadata entries)
    Empty string = root.
    """
    fp = (doc.get("folder_path") or "").strip().strip("/")
    if fp:
        return fp
    # Legacy fallback — filenames used to contain path info in some uploads.
    parent = Path(doc.get("filename", "")).parent
    return "" if str(parent) in ("", ".") else str(parent)


def _resolve_link_target(target_name: str, docs: list[dict]) -> str | None:
    """Resolve a [[wikilink]] target name to a document ID.

    Matching strategy (in order):
      1. Exact filename match (case-insensitive, with or without extension)
      2. Filename starts with target (e.g. [[API]] matches "API.docx")
      3. Target is a substring of filename

    Returns the document ID or None if no match.
    """
    target_lower = target_name.lower().strip()
    if not target_lower:
        return None

    # Pass 1: exact match (filename without extension)
    for doc in docs:
        fname = doc.get("filename", "")
        stem = Path(fname).stem.lower()
        if stem == target_lower or fname.lower() == target_lower:
            return doc.get("id")

    # Pass 2: filename starts with target
    for doc in docs:
        fname = doc.get("filename", "")
        stem = Path(fname).stem.lower()
        if stem.startswith(target_lower):
            return doc.get("id")

    # Pass 3: substring match
    for doc in docs:
        fname = doc.get("filename", "")
        if target_lower in fname.lower():
            return doc.get("id")

    return None


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


async def build_document_graph() -> GraphData:
    """Build the knowledge graph from [[wikilinks]] stored in document metadata.

    Returns GraphData with nodes (all documents) and links (resolved wikilinks).
    Documents without wikilinks appear as orphan nodes.
    """
    docs = _load_documents_index()

    # Build nodes for all documents.
    nodes: list[GraphNode] = []
    for doc in docs:
        filename = doc.get("filename", "")
        nodes.append(
            GraphNode(
                id=doc.get("id", ""),
                label=filename,
                folder=_folder_of(doc),
                chunks_count=int(doc.get("chunks_count", 0)),
                size_bytes=int(doc.get("size_bytes", 0)),
                uploaded_at=doc.get("uploaded_at", ""),
                file_ext=Path(filename).suffix.lower(),
            )
        )

    # Build edges from wikilinks.
    links: list[GraphLink] = []
    seen_pairs: set[tuple[str, str]] = set()

    for doc in docs:
        source_id = doc.get("id", "")
        wikilinks = doc.get("wikilinks", [])

        for wl in wikilinks:
            target_name = wl.get("target", "")
            target_id = _resolve_link_target(target_name, docs)

            if not target_id or target_id == source_id:
                continue

            # Deduplicate: A→B and B→A count as one edge.
            pair = tuple(sorted([source_id, target_id]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            links.append(
                GraphLink(
                    source=source_id,
                    target=target_id,
                    weight=1.0,
                    context=wl.get("context", ""),
                )
            )

    logger.info("Graph built — %d nodes, %d links (wikilinks only)", len(nodes), len(links))

    return GraphData(
        nodes=nodes,
        links=links,
        meta=GraphMeta(
            total_docs=len(nodes),
            total_links=len(links),
            generated_at=datetime.now(timezone.utc).isoformat(),
            cached=False,
        ),
    )


# ---------------------------------------------------------------------------
# Stats (cheap — no graph computation)
# ---------------------------------------------------------------------------


def get_graph_stats() -> GraphStats:
    """Return counts without computing the full graph."""
    docs = _load_documents_index()
    total_chunks = sum(int(d.get("chunks_count", 0)) for d in docs)

    cache_path = Path(settings.chroma_persist_dir) / "graph_cache.json"
    return GraphStats(
        total_docs=len(docs),
        total_chunks=total_chunks,
        cache_exists=cache_path.exists(),
    )
