"""Files router — serve generated images and other static files."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/files/generated/{filename}")
async def serve_generated_file(filename: str) -> FileResponse:
    """Serve a generated file (e.g. AI-generated images).

    Only serves files from the uploads/generated/ directory.
    """
    # Sanitize filename — no path traversal
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = Path(settings.upload_dir) / "generated" / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    # Detect content type
    suffix = file_path.suffix.lower()
    content_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }
    media_type = content_types.get(suffix, "application/octet-stream")

    return FileResponse(file_path, media_type=media_type)
