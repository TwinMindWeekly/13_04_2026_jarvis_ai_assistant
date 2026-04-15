"""Vault API router — serve converted Markdown documents."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vault")


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
