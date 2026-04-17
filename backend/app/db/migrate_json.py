"""Idempotent migration from ``uploads/documents_metadata.json`` → SQLite.

Runs on every app startup:
  1. If DB has any ``Document`` rows → skip (migration already done).
  2. If the JSON file does not exist → skip.
  3. Otherwise: upsert every JSON entry into ``documents`` + ``wikilinks``
     tables, then rename the JSON file to ``*.migrated`` so the next boot
     is a no-op.

Wikilinks in the old JSON were stored as ``{"target": str, "context": str}``
without a resolved target_doc_id — we resolve them via ``find_document_by_name``
after all documents are inserted.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.db.connection import session_scope
from app.db.models import Document, Wikilink
from app.db.services.documents import find_document_by_name

logger = logging.getLogger(__name__)

_JSON_NAME = "documents_metadata.json"
_DONE_SUFFIX = ".migrated"


def _json_path() -> Path:
    upload_dir = Path(settings.upload_dir)
    if not upload_dir.is_absolute():
        backend_root = Path(__file__).resolve().parent.parent.parent
        upload_dir = backend_root / upload_dir
    return upload_dir / _JSON_NAME


async def migrate_json_if_needed() -> dict:
    """Return a summary dict: {skipped|migrated, docs, links}."""
    path = _json_path()
    if not path.exists():
        return {"status": "skipped", "reason": "no_json", "docs": 0, "links": 0}

    async with session_scope() as session:
        any_doc = (await session.execute(select(Document.id).limit(1))).first()
        if any_doc is not None:
            logger.info("JSON → SQLite migration: DB already populated, skipping")
            return {"status": "skipped", "reason": "db_not_empty", "docs": 0, "links": 0}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("JSON migration: could not parse %s — %s", path, exc)
        return {"status": "skipped", "reason": "parse_error", "docs": 0, "links": 0}

    if not isinstance(raw, list) or not raw:
        # Still rename so we don't parse again
        _mark_done(path)
        return {"status": "skipped", "reason": "empty", "docs": 0, "links": 0}

    inserted_docs = 0
    inserted_links = 0

    async with session_scope() as session:
        # Pass 1 — documents only, so wikilink resolution has everything available.
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            doc_id = entry.get("id")
            if not doc_id:
                continue
            existing = await session.get(Document, doc_id)
            if existing:
                continue
            session.add(
                Document(
                    id=doc_id,
                    filename=entry.get("filename") or "",
                    size_bytes=int(entry.get("size_bytes") or 0),
                    chunks_count=int(entry.get("chunks_count") or 0),
                    uploaded_at=entry.get("uploaded_at") or "",
                    folder_path=(entry.get("folder_path") or "").strip().strip("/"),
                    sort_order=int(entry.get("sort_order") or 0),
                    vault_file=entry.get("vault_file") or "",
                    tags="[]",
                )
            )
            inserted_docs += 1
        await session.flush()

        # Pass 2 — wikilinks resolved against the freshly inserted docs.
        for entry in raw:
            doc_id = entry.get("id") if isinstance(entry, dict) else None
            if not doc_id:
                continue
            wikilinks = entry.get("wikilinks") or []
            seen: set[str] = set()
            for wl in wikilinks:
                if not isinstance(wl, dict):
                    continue
                target_name = (wl.get("target") or "").strip()
                if not target_name or target_name.lower() in seen:
                    continue
                seen.add(target_name.lower())
                target_doc = await find_document_by_name(session, target_name)
                session.add(
                    Wikilink(
                        source_doc_id=doc_id,
                        target_doc_id=(
                            target_doc.id if target_doc and target_doc.id != doc_id else None
                        ),
                        target_name=target_name,
                        display=(wl.get("display") or target_name).strip(),
                        context=(wl.get("context") or "").strip(),
                    )
                )
                inserted_links += 1

    _mark_done(path)
    logger.info(
        "JSON → SQLite migration complete: %d docs, %d wikilinks → %s",
        inserted_docs,
        inserted_links,
        path.name,
    )
    return {"status": "migrated", "docs": inserted_docs, "links": inserted_links}


def _mark_done(path: Path) -> None:
    try:
        target = path.with_suffix(path.suffix + _DONE_SUFFIX)
        if target.exists():
            target.unlink()
        path.rename(target)
    except Exception as exc:
        logger.warning("JSON migration: could not rename %s → .migrated — %s", path, exc)
