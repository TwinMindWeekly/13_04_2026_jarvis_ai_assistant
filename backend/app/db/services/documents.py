"""Document CRUD + query helpers built on top of SQLAlchemy.

These helpers encapsulate every read/write path used by the router, graph
builder, and the new ``doc_query`` tool so JSON doesn't leak into callers.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import session_scope
from app.db.models import Document, Wikilink

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def document_to_dict(doc: Document) -> dict:
    """Shape a Document row into the dict the API + graph layer expect."""
    try:
        tags = json.loads(doc.tags) if doc.tags else []
    except Exception:
        tags = []
    return {
        "id": doc.id,
        "filename": doc.filename,
        "size_bytes": doc.size_bytes,
        "chunks_count": doc.chunks_count,
        "uploaded_at": doc.uploaded_at,
        "folder_path": doc.folder_path,
        "sort_order": doc.sort_order,
        "vault_file": doc.vault_file,
        "tags": tags,
    }


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


async def list_documents(session: AsyncSession) -> list[Document]:
    result = await session.execute(select(Document).order_by(Document.sort_order, Document.uploaded_at))
    return list(result.scalars().all())


async def list_documents_as_dicts() -> list[dict]:
    async with session_scope() as session:
        rows = await list_documents(session)
        return [document_to_dict(d) for d in rows]


async def get_document(session: AsyncSession, doc_id: str) -> Document | None:
    return await session.get(Document, doc_id)


async def get_document_as_dict(doc_id: str) -> dict | None:
    async with session_scope() as session:
        doc = await get_document(session, doc_id)
        return document_to_dict(doc) if doc else None


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


async def create_document(
    session: AsyncSession,
    *,
    doc_id: str,
    filename: str,
    size_bytes: int,
    chunks_count: int,
    folder_path: str = "",
    vault_file: str = "",
    sort_order: int = 0,
    uploaded_at: str | None = None,
) -> Document:
    doc = Document(
        id=doc_id,
        filename=filename,
        size_bytes=size_bytes,
        chunks_count=chunks_count,
        uploaded_at=uploaded_at or datetime.now(timezone.utc).isoformat(),
        folder_path=folder_path,
        sort_order=sort_order,
        vault_file=vault_file,
        tags="[]",
    )
    session.add(doc)
    await session.flush()
    return doc


async def update_document_fields(
    session: AsyncSession,
    doc_id: str,
    *,
    filename: str | None = None,
    folder_path: str | None = None,
    sort_order: int | None = None,
    vault_file: str | None = None,
    chunks_count: int | None = None,
    size_bytes: int | None = None,
) -> Document | None:
    doc = await session.get(Document, doc_id)
    if not doc:
        return None
    if filename is not None and filename.strip():
        doc.filename = filename.strip()
    if folder_path is not None:
        doc.folder_path = folder_path.strip().strip("/")
    if sort_order is not None:
        doc.sort_order = sort_order
    if vault_file is not None:
        doc.vault_file = vault_file
    if chunks_count is not None:
        doc.chunks_count = chunks_count
    if size_bytes is not None:
        doc.size_bytes = size_bytes
    await session.flush()
    return doc


async def delete_document(session: AsyncSession, doc_id: str) -> bool:
    doc = await session.get(Document, doc_id)
    if not doc:
        return False
    await session.delete(doc)
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Bulk reorder
# ---------------------------------------------------------------------------


async def reorder_documents(session: AsyncSession, items: Iterable[dict]) -> int:
    updated = 0
    for item in items:
        doc_id = item.get("id")
        if not doc_id:
            continue
        doc = await session.get(Document, doc_id)
        if not doc:
            continue
        if "sort_order" in item and item["sort_order"] is not None:
            doc.sort_order = int(item["sort_order"])
        if "folder_path" in item and item["folder_path"] is not None:
            doc.folder_path = str(item["folder_path"]).strip().strip("/")
        updated += 1
    await session.flush()
    return updated


# ---------------------------------------------------------------------------
# Lookup helpers used by the graph + doc_query tool
# ---------------------------------------------------------------------------


async def find_document_by_name(session: AsyncSession, target_name: str) -> Document | None:
    """Resolve a wikilink target to a document using filename matching.

    Priority:
      1. Exact filename match (case-insensitive, with/without extension)
      2. Filename stem starts with the target
      3. Target is a substring of the filename
    """
    target = (target_name or "").strip().lower()
    if not target:
        return None
    rows = (await session.execute(select(Document))).scalars().all()

    def _stem(fname: str) -> str:
        return Path(fname).stem.lower()

    for doc in rows:
        fname = doc.filename or ""
        if _stem(fname) == target or fname.lower() == target:
            return doc
    for doc in rows:
        if _stem(doc.filename or "").startswith(target):
            return doc
    for doc in rows:
        if target in (doc.filename or "").lower():
            return doc
    return None


# ---------------------------------------------------------------------------
# Wikilink helpers
# ---------------------------------------------------------------------------


async def replace_outgoing_wikilinks(
    session: AsyncSession,
    source_doc_id: str,
    extracted: Iterable[dict],
) -> int:
    """Delete all wikilinks emitted by ``source_doc_id`` and insert fresh rows.

    ``extracted`` is the output of ``graph.link_extractor.extract_wikilinks``:
        [{target, display, context, ...}]
    Each target is resolved to a ``target_doc_id`` via filename matching.
    """
    await session.execute(delete(Wikilink).where(Wikilink.source_doc_id == source_doc_id))
    count = 0
    seen_targets: set[str] = set()
    for raw in extracted:
        target_name = (raw.get("target") or "").strip()
        if not target_name or target_name.lower() in seen_targets:
            continue
        seen_targets.add(target_name.lower())
        target_doc = await find_document_by_name(session, target_name)
        link = Wikilink(
            source_doc_id=source_doc_id,
            target_doc_id=(target_doc.id if target_doc and target_doc.id != source_doc_id else None),
            target_name=target_name,
            display=(raw.get("display") or target_name).strip(),
            context=(raw.get("context") or "").strip(),
        )
        session.add(link)
        count += 1
    await session.flush()
    return count


async def list_outgoing_wikilinks(session: AsyncSession, source_doc_id: str) -> list[Wikilink]:
    result = await session.execute(
        select(Wikilink).where(Wikilink.source_doc_id == source_doc_id)
    )
    return list(result.scalars().all())


async def list_backlinks(session: AsyncSession, target_doc_id: str) -> list[Wikilink]:
    result = await session.execute(
        select(Wikilink).where(Wikilink.target_doc_id == target_doc_id)
    )
    return list(result.scalars().all())


async def find_by_wikilink_target(session: AsyncSession, target_name: str) -> list[Wikilink]:
    """Case-insensitive match against ``target_name`` OR against the resolved doc filename."""
    needle = (target_name or "").strip().lower()
    if not needle:
        return []
    # direct literal match on the target_name column
    stmt = select(Wikilink).where(Wikilink.target_name.ilike(f"%{needle}%"))
    rows = list((await session.execute(stmt)).scalars().all())
    # Also include links resolved to a doc whose filename matches
    target_doc = await find_document_by_name(session, target_name)
    if target_doc:
        extra = await session.execute(
            select(Wikilink).where(Wikilink.target_doc_id == target_doc.id)
        )
        for link in extra.scalars().all():
            if link.id not in {r.id for r in rows}:
                rows.append(link)
    return rows
