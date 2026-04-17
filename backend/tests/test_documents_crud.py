"""Unit tests for documents metadata helpers and schema migrations.

Focuses on schema validation (Pydantic models) + round-trip of the
SQLite-backed metadata helpers exposed by ``app.routers.documents``.
"""

from __future__ import annotations

from app.models.document_schemas import (
    CreateDocRequest,
    DocumentInfo,
    UpdateDocRequest,
)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_document_info_folder_path_default_empty():
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
# Metadata round-trip (SQLite-backed)
# ---------------------------------------------------------------------------


def test_metadata_roundtrip_with_folder_path(temp_db):
    """Write → read → write cycle preserves folder_path via the DB."""
    from app.routers import documents as docs_router

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

    loaded[0]["folder_path"] = "Projects/Personal"
    loaded[0]["filename"] = "guide-renamed.md"
    docs_router._save_metadata(loaded)

    reloaded = docs_router._load_metadata()
    assert reloaded[0]["folder_path"] == "Projects/Personal"
    assert reloaded[0]["filename"] == "guide-renamed.md"


def test_metadata_empty_db_returns_empty_list(temp_db):
    from app.routers import documents as docs_router

    assert docs_router._load_metadata() == []
