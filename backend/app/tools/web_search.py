"""Web search tool using DuckDuckGo (no API key required)."""

import logging

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Search the internet via DuckDuckGo and return structured results."""

    name = "web_search"
    description = (
        "Search the internet for current information. "
        "Use this when you need to find facts, news, or answers to questions "
        "about current events."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def execute(self, query: str, num_results: int = 5) -> ToolResult:  # type: ignore[override]
        """Run a DuckDuckGo text search and return the top results.

        Args:
            query:       The search string.
            num_results: Maximum number of results to return (default 5).

        Returns:
            ToolResult with a list of ``{"title", "snippet", "url"}`` dicts on
            success, or an error message on failure.
        """
        logger.info("WebSearchTool executing — query=%r num_results=%d", query, num_results)

        try:
            import asyncio
            from ddgs import DDGS  # ddgs v9 (replaces deprecated duckduckgo_search)

            def _search():
                return list(DDGS().text(query, max_results=num_results) or [])

            raw_results = await asyncio.to_thread(_search)

            # Normalise to a consistent output schema regardless of DDG changes.
            data = [
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                }
                for r in (raw_results or [])
            ]

            logger.info("WebSearchTool found %d results for %r", len(data), query)
            return ToolResult(
                success=True,
                data=data,
                metadata={"query": query, "count": len(data)},
            )

        except Exception as exc:
            logger.error("WebSearchTool failed for query=%r: %s", query, exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))
