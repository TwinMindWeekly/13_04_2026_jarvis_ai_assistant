"""Knowledge graph API router — returns document similarity network."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.graph import (
    build_document_graph,
    get_graph_stats,
    invalidate_cache,
    load_cache,
    save_cache,
)
from app.graph.cache import cache_key
from app.graph.builder import _load_documents_index
from app.models.graph_schemas import GraphData, GraphStats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph")


@router.get("/data", response_model=GraphData)
async def get_graph(
    threshold: float = Query(0.5, ge=0.0, le=1.0, description="Edge similarity threshold"),
    force: bool = Query(False, description="Force recompute and overwrite cache"),
) -> GraphData:
    """Return the document similarity graph, using cache when possible."""
    docs = _load_documents_index()
    doc_ids = [d.get("id", "") for d in docs]
    key = cache_key(doc_ids, threshold)

    if not force:
        cached = load_cache(key)
        if cached is not None:
            # Mark the response so the UI knows it came from cache.
            cached.meta.cached = True
            logger.info(
                "Graph cache hit — %d nodes, %d links",
                len(cached.nodes),
                len(cached.links),
            )
            return cached

    try:
        data = await build_document_graph(threshold)
    except Exception as exc:
        logger.exception("Graph build failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Graph build failed: {exc}") from exc

    save_cache(key, data)
    return data


@router.get("/stats", response_model=GraphStats)
async def stats() -> GraphStats:
    """Cheap stats — no similarity computation, just counts."""
    return get_graph_stats()


@router.post("/rebuild", response_model=GraphData)
async def rebuild(
    threshold: float = Query(0.5, ge=0.0, le=1.0),
) -> GraphData:
    """Invalidate cache and rebuild the graph from scratch."""
    invalidate_cache()
    return await get_graph(threshold=threshold, force=True)
