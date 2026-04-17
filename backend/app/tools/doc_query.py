"""doc_query tool — structured metadata + wikilink lookups over the document DB.

Use instead of ``rag_search`` when the user is asking about **which files
exist, how they are linked, or where they live** — not about the *content*
of a file. The agent can then call ``read_doc`` to pull the full Markdown
only for the files that actually match.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.db.connection import session_scope
from app.db.models import Document, Wikilink
from app.db.services.documents import (
    document_to_dict,
    find_by_wikilink_target,
    list_backlinks,
    list_outgoing_wikilinks,
)
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

_MAX_READ_CHARS = 25_000


class DocQueryTool(BaseTool):
    name = "doc_query"
    description = (
        "Query document metadata and wikilinks (structured lookups over the user's knowledge base). "
        "Actions: "
        "find_by_wikilink (files linking to a target name), "
        "find_backlinks (files linking to a specific doc_id), "
        "list_by_folder (files in a folder), "
        "list_all (every document with metadata), "
        "get_metadata (one document's metadata), "
        "read_doc (full Markdown content of one vault file). "
        "Prefer this tool over rag_search when the user asks about file structure, links, folders, or a specific document by name."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "find_by_wikilink",
                    "find_backlinks",
                    "list_by_folder",
                    "list_all",
                    "get_metadata",
                    "read_doc",
                ],
                "description": "Query to perform.",
            },
            "target": {
                "type": "string",
                "description": "Wikilink target name (for find_by_wikilink).",
                "default": None,
            },
            "doc_id": {
                "type": "string",
                "description": "Document ID (for find_backlinks, get_metadata, read_doc).",
                "default": None,
            },
            "folder": {
                "type": "string",
                "description": "Folder path like 'Projects/Work'. Empty string = root. (for list_by_folder)",
                "default": None,
            },
            "limit": {
                "type": "integer",
                "description": "Max rows to return (default 50).",
                "default": 50,
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs) -> ToolResult:  # type: ignore[override]
        action = (kwargs.get("action") or "").lower()
        limit = int(kwargs.get("limit") or 50)
        try:
            if action == "find_by_wikilink":
                return await self._find_by_wikilink(kwargs.get("target") or "", limit)
            if action == "find_backlinks":
                return await self._find_backlinks(kwargs.get("doc_id") or "")
            if action == "list_by_folder":
                return await self._list_by_folder(kwargs.get("folder"), limit)
            if action == "list_all":
                return await self._list_all(limit)
            if action == "get_metadata":
                return await self._get_metadata(kwargs.get("doc_id") or "")
            if action == "read_doc":
                return await self._read_doc(kwargs.get("doc_id") or "")
            return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as exc:  # defensive — tools must never raise
            logger.exception("doc_query failed: %s", exc)
            return ToolResult(success=False, error=f"doc_query error: {exc}")

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _find_by_wikilink(self, target: str, limit: int) -> ToolResult:
        if not target.strip():
            return ToolResult(success=False, error="target is required for find_by_wikilink.")
        async with session_scope() as session:
            links = await find_by_wikilink_target(session, target)
            if not links:
                return ToolResult(
                    success=True,
                    data={"target": target, "count": 0, "matches": []},
                )
            source_ids = list({lnk.source_doc_id for lnk in links if lnk.source_doc_id})
            docs = {
                d.id: d
                for d in (
                    await session.execute(select(Document).where(Document.id.in_(source_ids)))
                ).scalars().all()
            }
            matches: list[dict] = []
            for lnk in links[:limit]:
                src = docs.get(lnk.source_doc_id)
                matches.append(
                    {
                        "doc_id": lnk.source_doc_id,
                        "filename": src.filename if src else "",
                        "folder_path": src.folder_path if src else "",
                        "target_name": lnk.target_name,
                        "context": lnk.context,
                    }
                )
        return ToolResult(
            success=True,
            data={"target": target, "count": len(matches), "matches": matches},
        )

    async def _find_backlinks(self, doc_id: str) -> ToolResult:
        if not doc_id.strip():
            return ToolResult(success=False, error="doc_id is required for find_backlinks.")
        async with session_scope() as session:
            doc = await session.get(Document, doc_id)
            if not doc:
                return ToolResult(success=False, error=f"Document not found: {doc_id}")
            links = await list_backlinks(session, doc_id)
            source_ids = list({lnk.source_doc_id for lnk in links})
            docs = {
                d.id: d
                for d in (
                    await session.execute(select(Document).where(Document.id.in_(source_ids)))
                ).scalars().all()
            }
            backlinks = [
                {
                    "doc_id": lnk.source_doc_id,
                    "filename": docs.get(lnk.source_doc_id).filename if docs.get(lnk.source_doc_id) else "",
                    "context": lnk.context,
                }
                for lnk in links
            ]
            outgoing = await list_outgoing_wikilinks(session, doc_id)
            outgoing_targets = [
                {
                    "target_name": o.target_name,
                    "resolved_doc_id": o.target_doc_id,
                    "context": o.context,
                }
                for o in outgoing
            ]
        return ToolResult(
            success=True,
            data={
                "doc_id": doc_id,
                "filename": doc.filename,
                "backlinks": backlinks,
                "backlinks_count": len(backlinks),
                "outgoing": outgoing_targets,
                "outgoing_count": len(outgoing_targets),
            },
        )

    async def _list_by_folder(self, folder: str | None, limit: int) -> ToolResult:
        target = (folder or "").strip().strip("/")
        async with session_scope() as session:
            stmt = select(Document).where(Document.folder_path == target).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            items = [document_to_dict(d) for d in rows]
        return ToolResult(
            success=True,
            data={"folder": target, "count": len(items), "documents": items},
        )

    async def _list_all(self, limit: int) -> ToolResult:
        async with session_scope() as session:
            rows = (
                await session.execute(
                    select(Document).order_by(Document.folder_path, Document.filename).limit(limit)
                )
            ).scalars().all()
            items = [document_to_dict(d) for d in rows]
        return ToolResult(success=True, data={"count": len(items), "documents": items})

    async def _get_metadata(self, doc_id: str) -> ToolResult:
        if not doc_id.strip():
            return ToolResult(success=False, error="doc_id is required for get_metadata.")
        async with session_scope() as session:
            doc = await session.get(Document, doc_id)
            if not doc:
                return ToolResult(success=False, error=f"Document not found: {doc_id}")
            data = document_to_dict(doc)
            # Include link counts so the agent can decide whether to drill deeper.
            out_links = await list_outgoing_wikilinks(session, doc_id)
            back_links = await list_backlinks(session, doc_id)
            data["outgoing_links_count"] = len(out_links)
            data["backlinks_count"] = len(back_links)
        return ToolResult(success=True, data=data)

    async def _read_doc(self, doc_id: str) -> ToolResult:
        if not doc_id.strip():
            return ToolResult(success=False, error="doc_id is required for read_doc.")
        async with session_scope() as session:
            doc = await session.get(Document, doc_id)
            if not doc:
                return ToolResult(success=False, error=f"Document not found: {doc_id}")

        # Prefer the vault Markdown file (has wikilinks); fall back to raw upload.
        vault_path = Path(settings.upload_dir) / "vault" / f"{doc_id}.md"
        if vault_path.exists():
            content = vault_path.read_text(encoding="utf-8")
        else:
            raw = next(
                (p for p in Path(settings.upload_dir).glob(f"{doc_id}.*") if p.is_file()),
                None,
            )
            if raw is None:
                return ToolResult(
                    success=False,
                    error=f"No vault or raw file for document {doc_id}.",
                )
            try:
                content = raw.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return ToolResult(success=False, error=f"Could not read file: {exc}")

        truncated = False
        if len(content) > _MAX_READ_CHARS:
            content = content[:_MAX_READ_CHARS]
            truncated = True
        return ToolResult(
            success=True,
            data={
                "doc_id": doc_id,
                "filename": doc.filename,
                "folder_path": doc.folder_path,
                "content": content,
                "truncated": truncated,
                "max_chars": _MAX_READ_CHARS,
            },
        )
