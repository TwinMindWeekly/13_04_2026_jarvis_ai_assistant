"""Web search tool using DuckDuckGo (no API key required)."""

import asyncio
import logging
from typing import Any

from app.tools.base import BaseTool, ToolResult
from app.tools._search_helpers import build_query, rerank_results

logger = logging.getLogger(__name__)


def _build_query(
    query: str,
    site: str = "",
    exact_phrase: str = "",
    exclude: list[str] | None = None,
    filetype: str = "",
) -> str:
    """Build an augmented DuckDuckGo query string with search operators.

    Pure helper — delegates to ``_search_helpers.build_query``.

    Args:
        query:        Base search query.
        site:         If non-empty, appends ``site:<domain>`` to restrict results.
        exact_phrase: If non-empty, wraps in double-quotes and appends.
        exclude:      Terms to exclude; each is prefixed with ``-``.
        filetype:     If non-empty, appends ``filetype:<ext>``.

    Returns:
        Augmented query string ready for DDGS.
    """
    return build_query(query, site=site, exact_phrase=exact_phrase, exclude=exclude, filetype=filetype)


class WebSearchTool(BaseTool):
    """Search the internet via DuckDuckGo and return structured results."""

    name = "web_search"
    description = (
        "PRIMARY tool for ALL internet searches. Use this FIRST for any question about "
        "weather, news, facts, people, events, or any information lookup. "
        "Returns search results with titles, snippets, and URLs. "
        "Supports search operators: site (restrict to domain), exact_phrase, exclude (terms to omit), "
        "filetype, date_range (d/w/m/y), region, safe_search (on/moderate/off), and rerank (semantic reordering). "
        "Do NOT use web_browser or browser_control for searching — use this tool instead."
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
            "site": {
                "type": "string",
                "description": "Restrict results to this domain (e.g. 'github.com'). Appends site:<domain> to query.",
                "default": "",
            },
            "exact_phrase": {
                "type": "string",
                "description": "Require this exact phrase in results. Will be wrapped in double quotes.",
                "default": "",
            },
            "exclude": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of terms to exclude from results. Each is prefixed with '-'.",
                "default": [],
            },
            "filetype": {
                "type": "string",
                "description": "Restrict results to this file type (e.g. 'pdf', 'doc').",
                "default": "",
            },
            "date_range": {
                "type": "string",
                "enum": ["d", "w", "m", "y"],
                "description": "Filter by recency: d=day, w=week, m=month, y=year.",
                "default": "",
            },
            "region": {
                "type": "string",
                "description": "DDGS region code (e.g. 'us-en', 'vn-vi'). Omit to use DDGS default (wt-wt).",
                "default": "",
            },
            "safe_search": {
                "type": "string",
                "enum": ["on", "moderate", "off"],
                "description": "Safe search level. Omit to use DDGS default.",
                "default": "",
            },
            "rerank": {
                "type": "boolean",
                "description": (
                    "If true, fetch num_results*3 from DDGS then rerank by semantic similarity "
                    "between the query and each result's title+snippet. Returns top num_results."
                ),
                "default": False,
            },
        },
        "required": ["query"],
    }

    async def execute(  # type: ignore[override]
        self,
        query: str,
        num_results: int = 5,
        site: str = "",
        exact_phrase: str = "",
        exclude: list[str] | None = None,
        filetype: str = "",
        date_range: str = "",
        region: str = "",
        safe_search: str = "",
        rerank: bool = False,
    ) -> ToolResult:
        """Run a DuckDuckGo text search and return the top results.

        Args:
            query:        The base search string.
            num_results:  Maximum number of results to return (default 5).
            site:         If set, restricts to a specific domain.
            exact_phrase: If set, requires this exact phrase in results.
            exclude:      Terms to exclude from results.
            filetype:     If set, restricts to a specific file type.
            date_range:   Recency filter: d=day, w=week, m=month, y=year.
            region:       DDGS region code (e.g. 'us-en').
            safe_search:  Safe search level: on, moderate, off.
            rerank:       If true, fetch 3x results and rerank by semantic similarity.

        Returns:
            ToolResult with a list of result dicts on success, or an error on failure.
        """
        logger.info(
            "WebSearchTool executing — query=%r num_results=%d rerank=%s",
            query, num_results, rerank,
        )

        try:
            from ddgs import DDGS  # ddgs v9 (replaces deprecated duckduckgo_search)

            augmented_query = _build_query(
                query,
                site=site,
                exact_phrase=exact_phrase,
                exclude=exclude,
                filetype=filetype,
            )

            # When reranking, fetch more results to have a bigger pool to score.
            fetch_count = num_results * 3 if rerank else num_results

            # Build optional DDGS kwargs.
            ddgs_kwargs: dict[str, Any] = {"max_results": fetch_count}
            if date_range:
                ddgs_kwargs["timelimit"] = date_range
            if region:
                ddgs_kwargs["region"] = region
            if safe_search:
                ddgs_kwargs["safesearch"] = safe_search

            def _search() -> list[dict[str, Any]]:
                return list(DDGS().text(augmented_query, **ddgs_kwargs) or [])

            raw_results: list[dict[str, Any]] = await asyncio.to_thread(_search)

            if not raw_results and (site or exact_phrase or exclude or filetype):
                logger.warning(
                    "WebSearchTool: zero results for complex query %r — consider simplifying operators",
                    augmented_query,
                )

            # Normalise to a consistent output schema regardless of DDGS key changes.
            data: list[dict[str, Any]] = [
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                    **({"date": r["date"]} if "date" in r else {}),
                }
                for r in (raw_results or [])
            ]

            if rerank and data:
                def _text_fn(item: dict[str, Any]) -> str:
                    return f"{item.get('title', '')} {item.get('snippet', '')}"

                data = await asyncio.to_thread(rerank_results, query, data, _text_fn, num_results)
            else:
                data = data[:num_results]

            logger.info("WebSearchTool found %d results for %r", len(data), augmented_query)
            return ToolResult(
                success=True,
                data=data,
                metadata={
                    "query": query,
                    "augmented_query": augmented_query,
                    "count": len(data),
                    "reranked": rerank,
                },
            )

        except Exception as exc:
            logger.error("WebSearchTool failed for query=%r: %s", query, exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))
