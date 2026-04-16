"""Pydantic schemas for the documents API."""

from pydantic import BaseModel


class DocumentInfo(BaseModel):
    id: str
    filename: str
    size_bytes: int
    chunks_count: int
    uploaded_at: str  # ISO 8601 format
    folder_path: str = ""  # e.g. "Projects/Work" — empty = root
    sort_order: int = 0  # manual sort position within folder


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    chunks_count: int
    message: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    total: int


class CreateDocRequest(BaseModel):
    filename: str
    folder_path: str = ""
    content: str = ""


class UpdateDocRequest(BaseModel):
    filename: str | None = None
    folder_path: str | None = None
    sort_order: int | None = None
