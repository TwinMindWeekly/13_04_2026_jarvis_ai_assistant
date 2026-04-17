"""Tests for the JSON → SQLite migration helper."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


def test_migrate_json_populates_db(temp_db, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.db.connection import session_scope
    from app.db.migrate_json import migrate_json_if_needed
    from app.db.models import Document, Wikilink
    from sqlalchemy import select

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    metadata = [
        {
            "id": "docA",
            "filename": "Python.md",
            "size_bytes": 500,
            "chunks_count": 2,
            "uploaded_at": "2026-04-15T00:00:00",
            "folder_path": "Languages",
            "wikilinks": [],
        },
        {
            "id": "docB",
            "filename": "Django.md",
            "size_bytes": 200,
            "chunks_count": 1,
            "uploaded_at": "2026-04-15T00:00:00",
            "folder_path": "Frameworks",
            "wikilinks": [{"target": "Python", "context": "Django uses [[Python]]."}],
        },
    ]
    json_path = tmp_path / "documents_metadata.json"
    json_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = asyncio.run(migrate_json_if_needed())
    assert result["status"] == "migrated"
    assert result["docs"] == 2
    assert result["links"] == 1

    # JSON renamed to .migrated
    assert not json_path.exists()
    assert (tmp_path / "documents_metadata.json.migrated").exists()

    async def _check() -> tuple[list[str], list[tuple[str, str | None]]]:
        async with session_scope() as session:
            ids = [d.id for d in (await session.execute(select(Document))).scalars().all()]
            links = [
                (w.source_doc_id, w.target_doc_id)
                for w in (await session.execute(select(Wikilink))).scalars().all()
            ]
            return ids, links

    ids, links = asyncio.run(_check())
    assert set(ids) == {"docA", "docB"}
    # Link from Django → Python should resolve
    assert ("docB", "docA") in links


def test_migrate_skipped_when_db_not_empty(temp_db, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.db.connection import session_scope
    from app.db.migrate_json import migrate_json_if_needed
    from app.db.models import Document

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    # Pre-populate the DB
    async def _seed() -> None:
        async with session_scope() as session:
            session.add(
                Document(id="existing", filename="x.md", size_bytes=1, chunks_count=1, uploaded_at="")
            )

    asyncio.run(_seed())

    # Put a JSON file that should be ignored
    (tmp_path / "documents_metadata.json").write_text(
        json.dumps([{"id": "new", "filename": "y.md"}]), encoding="utf-8"
    )

    result = asyncio.run(migrate_json_if_needed())
    assert result["status"] == "skipped"
    assert result["reason"] == "db_not_empty"


def test_migrate_skipped_when_no_json(temp_db, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.db.migrate_json import migrate_json_if_needed

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    result = asyncio.run(migrate_json_if_needed())
    assert result["status"] == "skipped"
    assert result["reason"] == "no_json"
