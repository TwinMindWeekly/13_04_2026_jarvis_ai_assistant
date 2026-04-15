"""Knowledge-graph module — build and cache document similarity graphs."""

from app.graph.builder import build_document_graph, get_graph_stats
from app.graph.cache import invalidate_cache, load_cache, save_cache

__all__ = [
    "build_document_graph",
    "get_graph_stats",
    "invalidate_cache",
    "load_cache",
    "save_cache",
]
