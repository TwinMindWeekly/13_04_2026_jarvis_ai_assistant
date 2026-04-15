"""Documents API router — upload, list, and delete user documents for RAG."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.models.document_schemas import (
    DocumentInfo,
    DocumentListResponse,
    DocumentUploadResponse,
)
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
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
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

    return {"id": doc_id, "deleted": True}
