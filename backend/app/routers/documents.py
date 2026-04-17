"""Documents API router — upload, list, edit, and delete user documents for RAG.

Metadata and wikilinks are persisted in SQLite via ``app.db`` instead of the
legacy ``uploads/documents_metadata.json`` file. The JSON file is migrated
on first startup (see ``app.db.migrate_json``).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.connection import get_session, session_scope
from app.db.models import Document
from app.db.services.documents import (
    create_document,
    delete_document,
    document_to_dict,
    get_document,
    list_documents,
    reorder_documents,
    replace_outgoing_wikilinks,
    update_document_fields,
)
from app.graph.cache import invalidate_cache as invalidate_graph_cache
from app.models.document_schemas import (
    CreateDocRequest,
    DocumentInfo,
    DocumentListResponse,
    DocumentUploadResponse,
    UpdateDocRequest,
)
from app.rag.document_parser import DocumentParser
from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents")

DEFAULT_COLLECTION = "jarvis_default"


# ---------------------------------------------------------------------------
# Back-compat helpers used by tests and the vault router.
# These read/write the same SQLite tables as the API.
# ---------------------------------------------------------------------------


def _load_metadata() -> list[dict]:
    """Synchronous wrapper — returns document dicts ordered by sort_order.

    Kept for back-compat with older tests. New code should use
    ``app.db.services.documents`` directly.
    """
    import asyncio  # noqa: PLC0415

    async def _run() -> list[dict]:
        async with session_scope() as session:
            rows = await list_documents(session)
            return [document_to_dict(d) for d in rows]

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # Nested event loop — create a new one on a thread.
        import concurrent.futures  # noqa: PLC0415

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(_run())).result()


def _save_metadata(docs: list[dict]) -> None:
    """Synchronous wrapper — replace the document set with the given dicts.

    Legacy callers (tests, vault router) pass a full list. We upsert every
    entry and delete anything missing from the input. New code should use
    the async service helpers instead.
    """
    import asyncio  # noqa: PLC0415

    async def _run() -> None:
        async with session_scope() as session:
            existing = await list_documents(session)
            existing_ids = {d.id for d in existing}
            given_ids: set[str] = set()
            for entry in docs:
                doc_id = entry.get("id")
                if not doc_id:
                    continue
                given_ids.add(doc_id)
                current = await session.get(Document, doc_id)
                if current is None:
                    session.add(
                        Document(
                            id=doc_id,
                            filename=entry.get("filename") or "",
                            size_bytes=int(entry.get("size_bytes") or 0),
                            chunks_count=int(entry.get("chunks_count") or 0),
                            uploaded_at=entry.get("uploaded_at")
                            or datetime.now(timezone.utc).isoformat(),
                            folder_path=(entry.get("folder_path") or "").strip().strip("/"),
                            sort_order=int(entry.get("sort_order") or 0),
                            vault_file=entry.get("vault_file") or "",
                            tags="[]",
                        )
                    )
                else:
                    if "filename" in entry and entry["filename"] is not None:
                        current.filename = entry["filename"]
                    if "folder_path" in entry and entry["folder_path"] is not None:
                        current.folder_path = str(entry["folder_path"]).strip().strip("/")
                    if "sort_order" in entry and entry["sort_order"] is not None:
                        current.sort_order = int(entry["sort_order"])
                    if "vault_file" in entry and entry["vault_file"] is not None:
                        current.vault_file = entry["vault_file"]
                    if "chunks_count" in entry and entry["chunks_count"] is not None:
                        current.chunks_count = int(entry["chunks_count"])
                    if "size_bytes" in entry and entry["size_bytes"] is not None:
                        current.size_bytes = int(entry["size_bytes"])
            for stale_id in existing_ids - given_ids:
                stale = await session.get(Document, stale_id)
                if stale is not None:
                    await session.delete(stale)
            # Wikilinks — if caller passed them, replace the outgoing set.
            from app.graph.link_extractor import extract_wikilinks  # noqa: PLC0415

            for entry in docs:
                doc_id = entry.get("id")
                if not doc_id:
                    continue
                wl = entry.get("wikilinks")
                if wl is None:
                    continue
                # Caller supplied partial dicts — synthesize extractor shape.
                synth = [
                    {"target": w.get("target", ""), "context": w.get("context", ""), "display": w.get("display", "")}
                    for w in wl
                    if isinstance(w, dict) and w.get("target")
                ]
                await replace_outgoing_wikilinks(session, doc_id, synth)

    try:
        asyncio.run(_run())
    except RuntimeError:
        import concurrent.futures  # noqa: PLC0415

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(lambda: asyncio.run(_run())).result()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    session: AsyncSession = Depends(get_session),
) -> DocumentUploadResponse:
    """Upload a document, parse into chunks, embed, store in ChromaDB + SQLite."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in DocumentParser.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: '{ext}'. Supported: {sorted(DocumentParser.SUPPORTED_EXTENSIONS)}",
        )

    doc_id = str(uuid.uuid4())
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{doc_id}{ext}"

    content = await file.read()
    file_path.write_bytes(content)
    logger.info("Saved uploaded file '%s' → %s (%d bytes)", file.filename, file_path, len(content))

    parser = DocumentParser()
    try:
        chunks = await parser.parse_file(str(file_path))
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        logger.error("Parsing failed for '%s': %s", file.filename, exc)
        raise HTTPException(status_code=422, detail=f"Failed to parse document: {exc}") from exc

    if not chunks:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="No content could be extracted from the document.")

    store = VectorStore()
    chunk_texts = [c["content"] for c in chunks]
    chunk_ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            **c.get("metadata", {}),
            "doc_id": doc_id,
            "filename": file.filename or "",
            "chunk_index": i,
        }
        for i, c in enumerate(chunks)
    ]
    try:
        await store.add_documents(DEFAULT_COLLECTION, chunk_texts, metadatas, chunk_ids)
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        logger.error("Embedding failed for '%s': %s", file.filename, exc)
        raise HTTPException(status_code=500, detail=f"Failed to index document: {exc}") from exc

    await create_document(
        session,
        doc_id=doc_id,
        filename=file.filename or "",
        size_bytes=len(content),
        chunks_count=len(chunks),
        folder_path="",
    )
    await session.commit()

    invalidate_graph_cache()

    if background_tasks:
        background_tasks.add_task(
            _process_vault_file,
            doc_id=doc_id,
            file_path=str(file_path),
            filename=file.filename or "",
        )

    logger.info("Indexed '%s' → %d chunks (doc_id=%s)", file.filename, len(chunks), doc_id)
    return DocumentUploadResponse(
        id=doc_id,
        filename=file.filename or "",
        chunks_count=len(chunks),
        message=f"Uploaded and indexed {len(chunks)} chunks successfully.",
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents_endpoint(
    session: AsyncSession = Depends(get_session),
) -> DocumentListResponse:
    rows = await list_documents(session)
    docs = [DocumentInfo(**{k: v for k, v in document_to_dict(d).items() if k in DocumentInfo.model_fields}) for d in rows]
    return DocumentListResponse(documents=docs, total=len(docs))


@router.post("/create", response_model=DocumentUploadResponse)
async def create_document_endpoint(
    body: CreateDocRequest,
    session: AsyncSession = Depends(get_session),
) -> DocumentUploadResponse:
    """Create a new empty markdown document directly in the vault."""
    filename = body.filename.strip() or "Untitled.md"
    if not filename.lower().endswith(".md"):
        filename = f"{filename}.md"

    doc_id = str(uuid.uuid4())
    content = body.content or ""
    folder_path = (body.folder_path or "").strip().strip("/")

    vault_dir = Path(settings.upload_dir) / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    vault_path = vault_dir / f"{doc_id}.md"
    vault_path.write_text(content, encoding="utf-8")

    chunks_count = 0
    if content.strip():
        store = VectorStore()
        try:
            await store.add_documents(
                DEFAULT_COLLECTION,
                [content],
                [{"doc_id": doc_id, "filename": filename, "chunk_index": 0}],
                [f"{doc_id}_0"],
            )
            chunks_count = 1
        except Exception as exc:
            logger.warning("Embed failed for new doc %s: %s", doc_id, exc)

    await create_document(
        session,
        doc_id=doc_id,
        filename=filename,
        size_bytes=len(content.encode("utf-8")),
        chunks_count=chunks_count,
        folder_path=folder_path,
        vault_file=str(vault_path),
    )

    # Extract wikilinks from seeded content.
    if content.strip():
        from app.graph.link_extractor import extract_wikilinks  # noqa: PLC0415

        extracted = extract_wikilinks(content, source_doc_id=doc_id)
        await replace_outgoing_wikilinks(session, doc_id, extracted)

    await session.commit()

    invalidate_graph_cache()
    logger.info("Created new document '%s' (doc_id=%s, folder='%s')", filename, doc_id, folder_path)
    return DocumentUploadResponse(
        id=doc_id,
        filename=filename,
        chunks_count=chunks_count,
        message="Document created successfully.",
    )


@router.patch("/{doc_id}", response_model=DocumentInfo)
async def update_document_endpoint(
    doc_id: str,
    body: UpdateDocRequest,
    session: AsyncSession = Depends(get_session),
) -> DocumentInfo:
    doc = await update_document_fields(
        session,
        doc_id,
        filename=body.filename,
        folder_path=body.folder_path,
        sort_order=body.sort_order,
    )
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")
    await session.commit()
    invalidate_graph_cache()
    data = document_to_dict(doc)
    return DocumentInfo(**{k: v for k, v in data.items() if k in DocumentInfo.model_fields})


@router.post("/reorder")
async def reorder_documents_endpoint(
    body: list[dict],
    session: AsyncSession = Depends(get_session),
) -> dict:
    updated = await reorder_documents(session, body)
    await session.commit()
    return {"updated": updated}


@router.delete("/{doc_id}")
async def delete_document_endpoint(
    doc_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    doc = await get_document(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

    # Remove vectors from ChromaDB (best effort).
    store = VectorStore()
    collection = store.get_or_create_collection(DEFAULT_COLLECTION)
    ids_to_delete = [f"{doc_id}_{i}" for i in range(doc.chunks_count)]
    try:
        collection.delete(ids=ids_to_delete)
        logger.info("Deleted %d vectors for doc_id=%s", len(ids_to_delete), doc_id)
    except Exception as exc:
        logger.warning("Could not delete vectors for doc_id=%s: %s", doc_id, exc)

    for ext in DocumentParser.SUPPORTED_EXTENSIONS:
        f = Path(settings.upload_dir) / f"{doc_id}{ext}"
        if f.exists():
            f.unlink()
            logger.info("Deleted file: %s", f)
            break

    await delete_document(session, doc_id)
    await session.commit()

    vault_path = Path(settings.upload_dir) / "vault" / f"{doc_id}.md"
    if vault_path.exists():
        vault_path.unlink()
        logger.info("Deleted vault file: %s", vault_path)

    invalidate_graph_cache()
    return {"id": doc_id, "deleted": True}


# ---------------------------------------------------------------------------
# Background task: convert → LLM wikilinks → vault .md → update DB
# ---------------------------------------------------------------------------


async def _process_vault_file(doc_id: str, file_path: str, filename: str) -> None:
    """Background task: convert document to Markdown, insert [[wikilinks]], persist.

    Non-fatal: if any step fails, the graph still shows the document as an
    orphan node.
    """
    from app.graph.link_extractor import extract_wikilinks  # noqa: PLC0415
    from app.rag.md_converter import MarkdownConverter  # noqa: PLC0415
    from app.rag.wikilink_generator import WikilinkGenerator  # noqa: PLC0415

    converter = MarkdownConverter()
    md_text = await converter.convert(file_path)
    if not md_text:
        logger.info("Vault skipped for '%s': conversion returned empty text", filename)
        return

    generator = WikilinkGenerator()
    md_with_links = await generator.generate(md_text)

    vault_dir = Path(settings.upload_dir) / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    vault_path = vault_dir / f"{doc_id}.md"
    vault_path.write_text(md_with_links, encoding="utf-8")

    extracted = extract_wikilinks(md_with_links, source_doc_id=doc_id)

    async with session_scope() as session:
        await update_document_fields(session, doc_id, vault_file=str(vault_path))
        await replace_outgoing_wikilinks(session, doc_id, extracted)

    invalidate_graph_cache()
    logger.info("Vault ready for '%s': %d wikilinks extracted", filename, len(extracted))
