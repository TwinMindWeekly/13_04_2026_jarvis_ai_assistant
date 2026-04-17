"""Unit tests for the ``doc_query`` tool."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.tools.doc_query import DocQueryTool


def _seed_graph(temp_db_path: Path) -> None:
    """Seed the DB with three docs + two wikilinks."""
    from app.db.connection import session_scope
    from app.db.models import Document, Wikilink

    async def _run() -> None:
        async with session_scope() as session:
            session.add_all(
                [
                    Document(
                        id="d1",
                        filename="Python.md",
                        size_bytes=1,
                        chunks_count=1,
                        uploaded_at="2026-04-15T00:00:00",
                        folder_path="Languages",
                    ),
                    Document(
                        id="d2",
                        filename="Django.md",
                        size_bytes=1,
                        chunks_count=1,
                        uploaded_at="",
                        folder_path="Frameworks",
                    ),
                    Document(
                        id="d3",
                        filename="Flask.md",
                        size_bytes=1,
                        chunks_count=1,
                        uploaded_at="",
                        folder_path="Frameworks",
                    ),
                    Wikilink(
                        source_doc_id="d2",
                        target_doc_id="d1",
                        target_name="Python",
                        display="Python",
                        context="Django uses [[Python]].",
                    ),
                    Wikilink(
                        source_doc_id="d3",
                        target_doc_id="d1",
                        target_name="Python",
                        display="Python",
                        context="Flask also uses [[Python]].",
                    ),
                ]
            )

    asyncio.run(_run())


def test_find_by_wikilink_returns_sources(temp_db):
    _seed_graph(temp_db)
    tool = DocQueryTool()
    result = asyncio.run(tool.execute(action="find_by_wikilink", target="Python"))
    assert result.success is True
    doc_ids = {m["doc_id"] for m in result.data["matches"]}
    assert doc_ids == {"d2", "d3"}
    assert result.data["count"] == 2


def test_find_backlinks_returns_sources(temp_db):
    _seed_graph(temp_db)
    tool = DocQueryTool()
    result = asyncio.run(tool.execute(action="find_backlinks", doc_id="d1"))
    assert result.success is True
    assert result.data["backlinks_count"] == 2
    assert {b["doc_id"] for b in result.data["backlinks"]} == {"d2", "d3"}


def test_list_by_folder(temp_db):
    _seed_graph(temp_db)
    tool = DocQueryTool()
    result = asyncio.run(tool.execute(action="list_by_folder", folder="Frameworks"))
    assert result.success is True
    assert result.data["count"] == 2
    assert {d["id"] for d in result.data["documents"]} == {"d2", "d3"}


def test_list_all(temp_db):
    _seed_graph(temp_db)
    tool = DocQueryTool()
    result = asyncio.run(tool.execute(action="list_all"))
    assert result.success is True
    assert result.data["count"] == 3


def test_get_metadata_includes_link_counts(temp_db):
    _seed_graph(temp_db)
    tool = DocQueryTool()
    result = asyncio.run(tool.execute(action="get_metadata", doc_id="d1"))
    assert result.success is True
    assert result.data["filename"] == "Python.md"
    assert result.data["backlinks_count"] == 2
    assert result.data["outgoing_links_count"] == 0


def test_read_doc_reads_vault_file(temp_db, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "d1.md").write_text("# Hello Python\n[[Django]]", encoding="utf-8")
    _seed_graph(temp_db)

    tool = DocQueryTool()
    result = asyncio.run(tool.execute(action="read_doc", doc_id="d1"))
    assert result.success is True
    assert "Hello Python" in result.data["content"]
    assert result.data["truncated"] is False


def test_unknown_action_errors(temp_db):
    tool = DocQueryTool()
    result = asyncio.run(tool.execute(action="does_not_exist"))
    assert result.success is False
    assert "Unknown action" in (result.error or "")
