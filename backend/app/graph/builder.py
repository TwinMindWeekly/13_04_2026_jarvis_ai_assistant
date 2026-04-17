"""Build a document knowledge graph from wikilink rows stored in SQLite.

Algorithm (Phase 1 DB refactor):
  1. SELECT every Document → graph node.
  2. SELECT every Wikilink with target_doc_id IS NOT NULL → edge.
  3. Deduplicate reciprocal edges (A→B collapses with B→A).

Link resolution happens at write-time inside
``app.db.services.documents.replace_outgoing_wikilinks``; this builder only
joins pre-resolved rows so it is O(n) in link count.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.db.connection import session_scope
from app.db.models import Document, Wikilink
from app.models.graph_schemas import (
    GraphData,
    GraphLink,
    GraphMeta,
    GraphNode,
    GraphStats,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers — kept for back-compat with existing tests.
# ---------------------------------------------------------------------------


def _folder_of(doc: dict) -> str:
    """Return the folder_path used for node colour grouping.

    Priority:
      1. Explicit ``folder_path`` field.
      2. Legacy fallback: parse parent from filename.
    """
    fp = (doc.get("folder_path") or "").strip().strip("/")
    if fp:
        return fp
    parent = Path(doc.get("filename", "")).parent
    return "" if str(parent) in ("", ".") else str(parent)


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


async def build_document_graph() -> GraphData:
    """Build the knowledge graph from pre-resolved wikilink rows."""
    async with session_scope() as session:
        docs = list((await session.execute(select(Document))).scalars().all())

        nodes: list[GraphNode] = []
        for doc in docs:
            filename = doc.filename or ""
            nodes.append(
                GraphNode(
                    id=doc.id,
                    label=filename.removesuffix(".md") if filename.endswith(".md") else filename,
                    folder=_folder_of({"filename": filename, "folder_path": doc.folder_path}),
                    chunks_count=int(doc.chunks_count or 0),
                    size_bytes=int(doc.size_bytes or 0),
                    uploaded_at=doc.uploaded_at or "",
                    file_ext=Path(filename).suffix.lower(),
                )
            )

        link_rows = list(
            (
                await session.execute(
                    select(Wikilink).where(Wikilink.target_doc_id.is_not(None))
                )
            )
            .scalars()
            .all()
        )

    links: list[GraphLink] = []
    seen_pairs: set[tuple[str, str]] = set()
    for wl in link_rows:
        source_id = wl.source_doc_id
        target_id = wl.target_doc_id
        if not source_id or not target_id or source_id == target_id:
            continue
        pair = tuple(sorted([source_id, target_id]))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        links.append(
            GraphLink(
                source=source_id,
                target=target_id,
                weight=1.0,
                context=wl.context or "",
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
# Stats
# ---------------------------------------------------------------------------


def get_graph_stats() -> GraphStats:
    """Return counts without computing the full graph."""
    import asyncio  # noqa: PLC0415

    async def _run() -> tuple[int, int]:
        async with session_scope() as session:
            docs = list((await session.execute(select(Document))).scalars().all())
            return len(docs), sum(int(d.chunks_count or 0) for d in docs)

    try:
        total_docs, total_chunks = asyncio.run(_run())
    except RuntimeError:
        import concurrent.futures  # noqa: PLC0415

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            total_docs, total_chunks = pool.submit(lambda: asyncio.run(_run())).result()

    cache_path = Path(settings.chroma_persist_dir) / "graph_cache.json"
    return GraphStats(
        total_docs=total_docs,
        total_chunks=total_chunks,
        cache_exists=cache_path.exists(),
    )
