"""Vault API router — serve and update converted Markdown documents."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vault")


class VaultSaveRequest(BaseModel):
    content: str


@router.get("/{doc_id}")
async def get_vault_file(doc_id: str) -> dict:
    """Return the converted Markdown content of a document.

    The vault file is created asynchronously after upload (background task).
    If it does not exist yet, the document may still be processing.
    """
    vault_path = Path(settings.upload_dir) / "vault" / f"{doc_id}.md"
    if not vault_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Vault file not found — document may still be processing.",
        )
    content = vault_path.read_text(encoding="utf-8")
    return {"doc_id": doc_id, "content": content}


@router.put("/{doc_id}")
async def save_vault_file(doc_id: str, body: VaultSaveRequest) -> dict:
    """Save edited Markdown content back to the vault file."""
    vault_dir = Path(settings.upload_dir) / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    vault_path = vault_dir / f"{doc_id}.md"
    if not vault_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Vault file not found — cannot save to a non-existent document.",
        )
    vault_path.write_text(body.content, encoding="utf-8")

    # Re-extract wikilinks from saved content and update metadata + graph cache.
    try:
        from app.graph.link_extractor import extract_wikilinks  # noqa: PLC0415
        from app.routers.documents import _load_metadata, _save_metadata  # noqa: PLC0415
        from app.graph.cache import invalidate_cache as invalidate_graph_cache  # noqa: PLC0415

        links = extract_wikilinks(body.content, source_doc_id=doc_id)
        docs = _load_metadata()
        for doc in docs:
            if doc["id"] == doc_id:
                doc["wikilinks"] = [
                    {"target": lnk["target"], "context": lnk["context"]}
                    for lnk in links
                ]
                break
        _save_metadata(docs)
        invalidate_graph_cache()
    except Exception as exc:
        logger.warning("Wikilink re-extraction failed for %s: %s", doc_id, exc)

    logger.info("Vault file saved: %s (%d wikilinks)", doc_id, len(links) if 'links' in dir() else 0)
    return {"doc_id": doc_id, "saved": True}
