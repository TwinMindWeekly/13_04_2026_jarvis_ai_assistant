"""Knowledge graph API router — returns document wikilink network."""

import logging

from fastapi import APIRouter, HTTPException, Query

from sqlalchemy import select

from app.db.connection import session_scope
from app.db.models import Document, Wikilink
from app.graph import (
    build_document_graph,
    get_graph_stats,
    invalidate_cache,
    load_cache,
    save_cache,
)
from app.graph.cache import cache_key
from app.models.graph_schemas import GraphData, GraphStats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph")


@router.get("/data", response_model=GraphData)
async def get_graph(
    force: bool = Query(False, description="Force recompute and overwrite cache"),
    # Keep threshold param for backward compat with frontend but ignore it.
    threshold: float = Query(0.5, include_in_schema=False),
) -> GraphData:
    """Return the document wikilink graph, using cache when possible."""
    async with session_scope() as session:
        doc_ids = [
            row[0]
            for row in (await session.execute(select(Document.id))).all()
        ]
        wikilink_count = len(
            (await session.execute(select(Wikilink.id))).all()
        )
    key = cache_key(doc_ids, float(wikilink_count))

    if not force:
        cached = load_cache(key)
        if cached is not None:
            cached.meta.cached = True
            logger.info(
                "Graph cache hit — %d nodes, %d links",
                len(cached.nodes),
                len(cached.links),
            )
            return cached

    try:
        data = await build_document_graph()
    except Exception as exc:
        logger.exception("Graph build failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Graph build failed: {exc}") from exc

    save_cache(key, data)
    return data


@router.get("/stats", response_model=GraphStats)
async def stats() -> GraphStats:
    """Cheap stats — no graph computation, just counts."""
    return get_graph_stats()


@router.post("/rebuild", response_model=GraphData)
async def rebuild() -> GraphData:
    """Invalidate cache and rebuild the graph from scratch."""
    invalidate_cache()
    return await get_graph(force=True)
