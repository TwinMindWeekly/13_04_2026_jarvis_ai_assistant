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
    logger.info("Vault file saved: %s", doc_id)
    return {"doc_id": doc_id, "saved": True}
