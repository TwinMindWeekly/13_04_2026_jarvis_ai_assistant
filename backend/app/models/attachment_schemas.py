"""Pydantic schemas for the chat attachment upload endpoint."""

from pydantic import BaseModel


class AttachmentUploadResponse(BaseModel):
    """Response body for POST /api/agent/upload-attachment."""

    filename: str
    content: str
    char_count: int
    truncated: bool
