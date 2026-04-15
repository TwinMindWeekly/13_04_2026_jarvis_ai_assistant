"""Pydantic schemas for the documents API."""

from pydantic import BaseModel


class DocumentInfo(BaseModel):
    id: str
    filename: str
    size_bytes: int
    chunks_count: int
    uploaded_at: str  # ISO 8601 format


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    chunks_count: int
    message: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    total: int
