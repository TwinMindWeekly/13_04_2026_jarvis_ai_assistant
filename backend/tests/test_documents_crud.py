"""Unit tests for documents metadata helpers and schema migrations.

Focuses on Part B changes (folder_path field, create/update flow).
Does not exercise the full FastAPI router (requires langgraph/LLM env).
"""

from __future__ import annotations

import json

from app.models.document_schemas import (
    CreateDocRequest,
    DocumentInfo,
    UpdateDocRequest,
)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_document_info_folder_path_default_empty():
    """Legacy metadata without folder_path should still parse."""
    legacy = {
        "id": "abc",
        "filename": "note.md",
        "size_bytes": 100,
        "chunks_count": 1,
        "uploaded_at": "2026-04-15T00:00:00",
    }
    info = DocumentInfo(**legacy)
    assert info.folder_path == ""


def test_document_info_folder_path_preserved():
    info = DocumentInfo(
        id="abc",
        filename="note.md",
        size_bytes=100,
        chunks_count=1,
        uploaded_at="2026-04-15T00:00:00",
        folder_path="Projects/Work",
    )
    assert info.folder_path == "Projects/Work"


def test_create_doc_request_defaults():
    body = CreateDocRequest(filename="hello.md")
    assert body.filename == "hello.md"
    assert body.folder_path == ""
    assert body.content == ""


def test_create_doc_request_full():
    body = CreateDocRequest(
        filename="hello.md",
        folder_path="Projects",
        content="# Hello\n",
    )
    assert body.folder_path == "Projects"
    assert body.content == "# Hello\n"


def test_update_doc_request_partial_filename_only():
    body = UpdateDocRequest(filename="renamed.md")
    assert body.filename == "renamed.md"
    assert body.folder_path is None


def test_update_doc_request_partial_folder_only():
    body = UpdateDocRequest(folder_path="NewFolder")
    assert body.filename is None
    assert body.folder_path == "NewFolder"


def test_update_doc_request_both():
    body = UpdateDocRequest(filename="x.md", folder_path="Y/Z")
    assert body.filename == "x.md"
    assert body.folder_path == "Y/Z"


def test_update_doc_request_empty_folder_to_root():
    body = UpdateDocRequest(folder_path="")
    assert body.folder_path == ""


# ---------------------------------------------------------------------------
# Metadata round-trip (simulates what the router does)
# ---------------------------------------------------------------------------


def test_metadata_roundtrip_with_folder_path(tmp_path, monkeypatch):
    """Write → read → write cycle preserves folder_path."""
    from app.core.config import settings
    from app.routers import documents as docs_router

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    initial = [
        {
            "id": "doc1",
            "filename": "guide.md",
            "size_bytes": 500,
            "chunks_count": 2,
            "uploaded_at": "2026-04-15T00:00:00",
            "folder_path": "Projects/Work",
        }
    ]
    docs_router._save_metadata(initial)

    loaded = docs_router._load_metadata()
    assert len(loaded) == 1
    assert loaded[0]["folder_path"] == "Projects/Work"

    # Simulate PATCH update
    loaded[0]["folder_path"] = "Projects/Personal"
    loaded[0]["filename"] = "guide-renamed.md"
    docs_router._save_metadata(loaded)

    reloaded = docs_router._load_metadata()
    assert reloaded[0]["folder_path"] == "Projects/Personal"
    assert reloaded[0]["filename"] == "guide-renamed.md"


def test_metadata_legacy_file_loads_without_folder_path(tmp_path, monkeypatch):
    """Old metadata.json without folder_path should still deserialize."""
    from app.core.config import settings
    from app.routers import documents as docs_router

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    # Legacy format — no folder_path field
    legacy = [
        {
            "id": "legacy1",
            "filename": "old.md",
            "size_bytes": 100,
            "chunks_count": 1,
            "uploaded_at": "2025-01-01T00:00:00",
        }
    ]
    (tmp_path / "documents_metadata.json").write_text(
        json.dumps(legacy), encoding="utf-8"
    )

    loaded = docs_router._load_metadata()
    assert len(loaded) == 1
    # DocumentInfo should apply default
    info = DocumentInfo(**loaded[0])
    assert info.folder_path == ""
