"""Attachment router — ephemeral file parsing for chat inline attachments.

Files are parsed server-side and returned as text. They are NOT stored
or indexed into ChromaDB — that's what the documents router is for.
"""

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, HTTPException, UploadFile

from app.models.attachment_schemas import AttachmentUploadResponse
from app.rag.document_parser import DocumentParser

logger = logging.getLogger(__name__)

router = APIRouter()

# Limits
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_CONTENT_CHARS = 100_000  # ~25K tokens

# Accepted extensions: document formats + code/data files
ACCEPTED_EXTENSIONS = {
    # Documents (same as DocumentParser)
    ".pdf", ".docx", ".txt", ".md", ".pptx", ".xlsx",
    # Code files
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h",
    ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".sh", ".bat", ".ps1",
    # Data/config files
    ".json", ".csv", ".html", ".css", ".yaml", ".yml", ".toml", ".xml",
    ".ini", ".cfg", ".env", ".log", ".sql", ".graphql",
    # Markup
    ".rst", ".tex", ".org",
}

_parser = DocumentParser()


@router.post("/api/agent/upload-attachment", response_model=AttachmentUploadResponse)
async def upload_attachment(file: UploadFile) -> AttachmentUploadResponse:
    """Parse an uploaded file and return its text content for chat injection.

    - Max 5 MB per file
    - Supported: documents, code, data files (see ACCEPTED_EXTENSIONS)
    - Content truncated to 100K chars if longer
    - File is NOT stored — ephemeral parse only
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ACCEPTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: '{ext}'. Accepted: documents, code, and data files.",
        )

    # Read file content with size check
    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(raw) / 1024 / 1024:.1f} MB). Maximum is 5 MB.",
        )

    # For code/text files, read directly as UTF-8
    text_extensions = ACCEPTED_EXTENSIONS - {".pdf", ".docx", ".pptx", ".xlsx"}
    if ext in text_extensions:
        content = raw.decode("utf-8", errors="replace")
    else:
        # Use DocumentParser for binary formats (PDF, DOCX, PPTX, XLSX)
        suffix = ext
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name

        try:
            chunks = await _parser.parse_file(tmp_path)
            content = "\n\n".join(chunk["content"] for chunk in chunks)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # Truncate if needed
    truncated = len(content) > MAX_CONTENT_CHARS
    if truncated:
        content = content[:MAX_CONTENT_CHARS] + "\n\n... (truncated)"

    logger.info(
        "Attachment parsed: %s (%d bytes → %d chars, truncated=%s)",
        file.filename, len(raw), len(content), truncated,
    )

    return AttachmentUploadResponse(
        filename=file.filename,
        content=content,
        char_count=len(content),
        truncated=truncated,
    )
