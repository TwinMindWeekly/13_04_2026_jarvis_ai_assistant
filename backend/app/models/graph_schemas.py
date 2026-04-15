"""Pydantic schemas for the knowledge-graph API."""

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """A single document represented as a node in the knowledge graph."""

    id: str = Field(..., description="Document ID (matches metadata index)")
    label: str = Field(..., description="Filename used as display label")
    folder: str = Field(default="", description="Parent folder path for color grouping")
    chunks_count: int = Field(default=0, description="Number of chunks — drives node size")
    size_bytes: int = Field(default=0, description="Original file size in bytes")
    uploaded_at: str = Field(default="", description="ISO 8601 upload timestamp")
    file_ext: str = Field(default="", description="File extension (e.g. '.pdf')")


class GraphLink(BaseModel):
    """An edge between two documents whose embeddings are similar."""

    source: str = Field(..., description="Source document ID")
    target: str = Field(..., description="Target document ID")
    weight: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity 0..1")


class GraphMeta(BaseModel):
    """Metadata about the generated graph."""

    total_docs: int = 0
    total_links: int = 0
    threshold: float = 0.5
    generated_at: str = ""
    cached: bool = False


class GraphData(BaseModel):
    """Complete graph payload returned to the frontend."""

    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)
    meta: GraphMeta = Field(default_factory=GraphMeta)


class GraphStats(BaseModel):
    """Lightweight statistics for the documents graph (no full payload)."""

    total_docs: int
    total_chunks: int
    cache_exists: bool
