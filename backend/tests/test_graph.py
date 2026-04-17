"""Unit tests for the knowledge-graph module."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.graph.builder import (
    _folder_of,
    build_document_graph,
    get_graph_stats,
)
from app.graph.cache import cache_key, invalidate_cache, load_cache, save_cache
from app.models.graph_schemas import GraphData, GraphMeta


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def test_folder_of_root_file():
    assert _folder_of({"filename": "file.pdf"}) == ""


def test_folder_of_nested_file():
    # Legacy fallback: filename with path
    assert _folder_of({"filename": "subdir/file.pdf"}) == "subdir"


def test_folder_of_uses_explicit_folder_path():
    # New field wins over filename parsing
    assert _folder_of({"filename": "file.pdf", "folder_path": "Projects/Work"}) == "Projects/Work"


def test_folder_of_empty_folder_path():
    # Empty folder_path falls back to filename parsing
    assert _folder_of({"filename": "sub/file.pdf", "folder_path": ""}) == "sub"


# ---------------------------------------------------------------------------
# Cache layer
# ---------------------------------------------------------------------------


def test_cache_key_is_deterministic():
    k1 = cache_key(["a", "b", "c"], 0.5)
    k2 = cache_key(["c", "b", "a"], 0.5)
    assert k1 == k2  # order-independent


def test_cache_key_changes_with_threshold():
    assert cache_key(["a", "b"], 0.5) != cache_key(["a", "b"], 0.7)


def test_cache_roundtrip(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path))

    data = GraphData(
        nodes=[],
        links=[],
        meta=GraphMeta(total_docs=0, total_links=0),
    )
    key = "abc123"
    save_cache(key, data)
    loaded = load_cache(key)
    assert loaded is not None
    assert loaded.meta.total_docs == 0

    invalidate_cache()
    assert load_cache(key) is None


def test_cache_miss_wrong_key(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path))

    save_cache("key1", GraphData())
    assert load_cache("key2") is None


# ---------------------------------------------------------------------------
# Builder — empty / insufficient state
# ---------------------------------------------------------------------------


def test_build_graph_empty_db(temp_db, tmp_path, monkeypatch):
    """Empty DB → empty graph, no error."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))

    data = asyncio.run(build_document_graph())
    assert len(data.nodes) == 0
    assert len(data.links) == 0


def test_build_graph_single_document(temp_db, tmp_path, monkeypatch):
    """1 document → 1 node, 0 links."""
    from app.core.config import settings
    from app.db.connection import session_scope
    from app.db.models import Document

    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))

    async def _seed() -> None:
        async with session_scope() as session:
            session.add(
                Document(
                    id="doc1",
                    filename="a.pdf",
                    size_bytes=100,
                    chunks_count=3,
                    uploaded_at="2026-04-15T00:00:00",
                )
            )

    asyncio.run(_seed())

    data = asyncio.run(build_document_graph())
    assert len(data.nodes) == 1
    assert len(data.links) == 0
    assert data.nodes[0].label == "a.pdf"
    assert data.nodes[0].file_ext == ".pdf"


def test_build_graph_resolves_wikilinks(temp_db, tmp_path, monkeypatch):
    """Wikilink rows with target_doc_id populate the link list."""
    from app.core.config import settings
    from app.db.connection import session_scope
    from app.db.models import Document, Wikilink

    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))

    async def _seed() -> None:
        async with session_scope() as session:
            session.add_all(
                [
                    Document(id="d1", filename="Python.md", size_bytes=1, chunks_count=1, uploaded_at=""),
                    Document(id="d2", filename="Django.md", size_bytes=1, chunks_count=1, uploaded_at=""),
                    Wikilink(
                        source_doc_id="d2",
                        target_doc_id="d1",
                        target_name="Python",
                        display="Python",
                        context="Django uses [[Python]].",
                    ),
                ]
            )

    asyncio.run(_seed())
    data = asyncio.run(build_document_graph())
    assert len(data.nodes) == 2
    assert len(data.links) == 1
    assert {data.links[0].source, data.links[0].target} == {"d1", "d2"}


def test_stats_counts_chunks(temp_db, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.db.connection import session_scope
    from app.db.models import Document

    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))

    async def _seed() -> None:
        async with session_scope() as session:
            session.add_all(
                [
                    Document(id="d1", filename="a.pdf", size_bytes=100, chunks_count=3, uploaded_at=""),
                    Document(id="d2", filename="b.pdf", size_bytes=200, chunks_count=7, uploaded_at=""),
                ]
            )

    asyncio.run(_seed())

    stats = get_graph_stats()
    assert stats.total_docs == 2
    assert stats.total_chunks == 10
    assert stats.cache_exists is False
