"""Documents API router — upload, list, and delete user documents for RAG."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.core.config import settings
from app.models.document_schemas import (
    DocumentInfo,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.graph.cache import invalidate_cache as invalidate_graph_cache
from app.rag.document_parser import DocumentParser
from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents")

DEFAULT_COLLECTION = "jarvis_default"
METADATA_FILE = "documents_metadata.json"


# ---------------------------------------------------------------------------
# Metadata index helpers
# ---------------------------------------------------------------------------


def _metadata_path() -> Path:
    return Path(settings.upload_dir) / METADATA_FILE


def _load_metadata() -> list[dict]:
    p = _metadata_path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to read metadata file: %s", exc)
        return []


def _save_metadata(docs: list[dict]) -> None:
    p = _metadata_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(docs, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
) -> DocumentUploadResponse:
    """Upload a document, parse it into chunks, embed and store in ChromaDB."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in DocumentParser.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: '{ext}'. Supported: {sorted(DocumentParser.SUPPORTED_EXTENSIONS)}",
        )

    # Save raw file
    doc_id = str(uuid.uuid4())
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{doc_id}{ext}"

    content = await file.read()
    file_path.write_bytes(content)
    logger.info("Saved uploaded file '%s' → %s (%d bytes)", file.filename, file_path, len(content))

    # Parse into chunks
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

    # Embed and store in ChromaDB
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

    # Persist metadata index
    docs = _load_metadata()
    info: dict = {
        "id": doc_id,
        "filename": file.filename or "",
        "size_bytes": len(content),
        "chunks_count": len(chunks),
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    docs.append(info)
    _save_metadata(docs)

    # Invalidate knowledge graph cache — next /api/graph/data call will rebuild.
    invalidate_graph_cache()

    # Background: convert to Markdown + LLM wikilinks → vault .md → update metadata.
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
async def list_documents() -> DocumentListResponse:
    """Return all uploaded documents with their metadata."""
    docs = _load_metadata()
    return DocumentListResponse(
        documents=[DocumentInfo(**d) for d in docs],
        total=len(docs),
    )


@router.delete("/{doc_id}")
async def delete_document(doc_id: str) -> dict:
    """Delete a document: remove from ChromaDB, delete the file, update metadata."""
    docs = _load_metadata()
    target = next((d for d in docs if d["id"] == doc_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

    # Remove vectors from ChromaDB
    store = VectorStore()
    collection = store.get_or_create_collection(DEFAULT_COLLECTION)
    ids_to_delete = [f"{doc_id}_{i}" for i in range(target["chunks_count"])]
    try:
        collection.delete(ids=ids_to_delete)
        logger.info("Deleted %d vectors for doc_id=%s", len(ids_to_delete), doc_id)
    except Exception as exc:
        logger.warning("Could not delete vectors for doc_id=%s: %s", doc_id, exc)

    # Delete the file (try all supported extensions)
    for ext in DocumentParser.SUPPORTED_EXTENSIONS:
        f = Path(settings.upload_dir) / f"{doc_id}{ext}"
        if f.exists():
            f.unlink()
            logger.info("Deleted file: %s", f)
            break

    # Update metadata index
    updated = [d for d in docs if d["id"] != doc_id]
    _save_metadata(updated)

    # Delete vault .md file if it exists.
    vault_path = Path(settings.upload_dir) / "vault" / f"{doc_id}.md"
    if vault_path.exists():
        vault_path.unlink()
        logger.info("Deleted vault file: %s", vault_path)

    # Invalidate knowledge graph cache.
    invalidate_graph_cache()

    return {"id": doc_id, "deleted": True}


# ---------------------------------------------------------------------------
# Background task: convert → LLM wikilinks → vault .md → update metadata
# ---------------------------------------------------------------------------


async def _process_vault_file(doc_id: str, file_path: str, filename: str) -> None:
    """Background task: convert document to Markdown, insert [[wikilinks]], save vault file.

    Non-fatal: if any step fails, the graph still shows nodes (orphan, no edges).
    """
    from app.rag.md_converter import MarkdownConverter  # noqa: PLC0415
    from app.rag.wikilink_generator import WikilinkGenerator  # noqa: PLC0415
    from app.graph.link_extractor import extract_wikilinks  # noqa: PLC0415

    # Step A: Convert to Markdown.
    converter = MarkdownConverter()
    md_text = await converter.convert(file_path)
    if not md_text:
        logger.info("Vault skipped for '%s': conversion returned empty text", filename)
        return

    # Step B: LLM insert [[wikilinks]].
    generator = WikilinkGenerator()
    md_with_links = await generator.generate(md_text)

    # Step C: Save to vault/ folder.
    vault_dir = Path(settings.upload_dir) / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    vault_path = vault_dir / f"{doc_id}.md"
    vault_path.write_text(md_with_links, encoding="utf-8")

    # Step D: Extract links and update metadata.
    links = extract_wikilinks(md_with_links, source_doc_id=doc_id)
    docs = _load_metadata()
    for doc in docs:
        if doc["id"] == doc_id:
            doc["vault_file"] = str(vault_path)
            doc["wikilinks"] = [
                {"target": lnk["target"], "context": lnk["context"]}
                for lnk in links
            ]
            break
    _save_metadata(docs)

    # Invalidate graph cache so next request rebuilds with new wikilinks.
    invalidate_graph_cache()
    logger.info("Vault ready for '%s': %d wikilinks extracted", filename, len(links))
