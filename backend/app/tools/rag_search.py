"""RAG search tool — searches user-uploaded documents via ChromaDB."""

import logging

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class RagSearchTool(BaseTool):
    """Search the user's uploaded documents for relevant information.

    Uses ChromaDB with local sentence-transformers embeddings.
    Should be preferred over web_search when the user asks about their
    files, documents, or knowledge base.
    """

    name = "rag_search"
    description = (
        "Search the user's uploaded documents for relevant information. "
        "Use this BEFORE web_search when the user asks about their files, documents, or knowledge base. "
        "Returns top-K matching chunks with citations (filename, chunk_id)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query to find relevant document chunks",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default: 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    DEFAULT_COLLECTION = "jarvis_default"

    async def execute(self, query: str, top_k: int = 5) -> ToolResult:  # type: ignore[override]
        """Search the vector store for document chunks matching the query."""
        try:
            from app.rag.vector_store import VectorStore

            store = VectorStore()
            results = await store.search(self.DEFAULT_COLLECTION, query, top_k)

            if not results:
                return ToolResult(
                    success=True,
                    data="No matching documents found.",
                    metadata={"count": 0},
                )

            return ToolResult(
                success=True,
                data=results,
                metadata={"count": len(results), "query": query},
            )
        except Exception as exc:
            logger.error("RagSearchTool.execute failed: %s", exc)
            return ToolResult(success=False, error=str(exc))
