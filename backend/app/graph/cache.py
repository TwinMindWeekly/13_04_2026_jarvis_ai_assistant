"""JSON file cache for the computed document graph.

Cache key is a hash of (sorted document ids, threshold). The cache is
invalidated whenever a document is uploaded or deleted so the next graph
request recomputes from fresh data.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from app.core.config import settings
from app.models.graph_schemas import GraphData

logger = logging.getLogger(__name__)

_CACHE_FILENAME = "graph_cache.json"


def _cache_path() -> Path:
    """Return the cache file path inside the Chroma persist directory."""
    return Path(settings.chroma_persist_dir) / _CACHE_FILENAME


def cache_key(doc_ids: list[str], threshold: float) -> str:
    """Deterministic key derived from sorted doc ids and the threshold."""
    payload = json.dumps(
        {"ids": sorted(doc_ids), "threshold": round(threshold, 3)},
        sort_keys=True,
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def load_cache(key: str) -> GraphData | None:
    """Return cached graph if the stored key matches, otherwise None."""
    path = _cache_path()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Graph cache corrupted (%s): %s — ignoring.", path, exc)
        return None

    if raw.get("_key") != key:
        return None

    try:
        return GraphData.model_validate(raw.get("data", {}))
    except Exception as exc:
        logger.warning("Graph cache payload invalid: %s — ignoring.", exc)
        return None


def save_cache(key: str, data: GraphData) -> None:
    """Persist graph data to disk, tagged with the cache key."""
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"_key": key, "data": data.model_dump()}
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
        logger.info("Graph cache saved (%d nodes, %d links).", len(data.nodes), len(data.links))
    except Exception as exc:
        logger.warning("Could not write graph cache: %s", exc)


def invalidate_cache() -> None:
    """Remove the cache file so the next request recomputes the graph."""
    path = _cache_path()
    try:
        path.unlink(missing_ok=True)
        logger.info("Graph cache invalidated.")
    except Exception as exc:
        logger.warning("Could not invalidate graph cache: %s", exc)
