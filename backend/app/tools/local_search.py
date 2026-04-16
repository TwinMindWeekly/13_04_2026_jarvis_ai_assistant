"""Local file search tool — find files by name or content on the user's machine."""

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any

from app.tools.base import BaseTool, ToolResult
from app.tools.safety import SafetyGuard

logger = logging.getLogger(__name__)

# Max results to return per search
_MAX_RESULTS = 20
# Max file size to search content in (skip large binaries)
_MAX_CONTENT_SEARCH_BYTES = 512_000  # 512 KB
# File extensions to search content in
_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".conf", ".html", ".css", ".csv",
    ".xml", ".sql", ".sh", ".bat", ".ps1", ".log", ".env", ".rst",
    ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp", ".rb", ".php",
}


def _search_by_name(directory: str, pattern: str, max_results: int) -> list[dict]:
    """Search for files matching a glob or substring pattern."""
    results = []
    pattern_lower = pattern.lower()
    root = Path(directory)

    if not root.is_dir():
        return []

    try:
        # Try glob first
        if any(c in pattern for c in ("*", "?", "[")):
            for p in root.rglob(pattern):
                if len(results) >= max_results:
                    break
                results.append(_file_info(p))
        else:
            # Substring match on filename
            for p in root.rglob("*"):
                if len(results) >= max_results:
                    break
                if pattern_lower in p.name.lower():
                    results.append(_file_info(p))
    except PermissionError:
        pass

    return results


def _search_by_content(
    directory: str, query: str, max_results: int
) -> list[dict]:
    """Search for files containing a text query."""
    results = []
    query_lower = query.lower()
    root = Path(directory)

    if not root.is_dir():
        return []

    try:
        for p in root.rglob("*"):
            if len(results) >= max_results:
                break
            if not p.is_file():
                continue
            if p.suffix.lower() not in _TEXT_EXTENSIONS:
                continue
            if p.stat().st_size > _MAX_CONTENT_SEARCH_BYTES:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                if query_lower in text.lower():
                    # Find matching lines for context
                    matches = []
                    for i, line in enumerate(text.splitlines(), 1):
                        if query_lower in line.lower():
                            matches.append({"line": i, "text": line.strip()[:200]})
                            if len(matches) >= 3:
                                break
                    info = _file_info(p)
                    info["matches"] = matches
                    results.append(info)
            except (OSError, UnicodeDecodeError):
                continue
    except PermissionError:
        pass

    return results


def _file_info(p: Path) -> dict:
    """Build a dict with basic file metadata."""
    try:
        stat = p.stat()
        size = stat.st_size
    except OSError:
        size = 0

    return {
        "path": str(p),
        "name": p.name,
        "is_dir": p.is_dir(),
        "size": size,
        "extension": p.suffix,
    }


class LocalSearchTool(BaseTool):
    """Search for files on the local filesystem by name or content.

    Useful for finding documents, code files, or any file the user has on
    their machine. Supports filename pattern matching and full-text content
    search within text files.
    """

    name = "local_search"
    description = (
        "Search for files on the user's computer by filename or content. "
        "Use mode='name' to find files by name pattern (glob or substring). "
        "Use mode='content' to search inside text files for a query. "
        "Returns file paths, sizes, and matching lines."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search query — filename pattern (e.g. '*.pdf', 'report') "
                    "or text to find inside files."
                ),
            },
            "directory": {
                "type": "string",
                "description": (
                    "Directory to search in. Defaults to user's home directory. "
                    "Examples: 'D:/projects', 'C:/Users/user/Documents'."
                ),
            },
            "mode": {
                "type": "string",
                "enum": ["name", "content"],
                "description": (
                    "'name' to search by filename, 'content' to search inside files. "
                    "Default: 'name'."
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Max results to return. Default: 20.",
            },
        },
        "required": ["query"],
    }

    async def execute(
        self,
        query: str,
        directory: str = "",
        mode: str = "name",
        max_results: int = _MAX_RESULTS,
        **_kwargs: Any,
    ) -> ToolResult:
        logger.info(
            "LocalSearchTool executing — query=%s dir=%s mode=%s",
            query, directory, mode,
        )

        if not query or not query.strip():
            return ToolResult(success=False, error="Query cannot be empty.")

        # Default directory: user's home
        if not directory:
            directory = str(Path.home())

        # Safety check on directory
        safety = SafetyGuard.check_file_path(directory, write=False)
        if not safety.allowed:
            return ToolResult(success=False, error=safety.reason)

        max_results = min(max_results, _MAX_RESULTS)

        try:
            if mode == "content":
                results = await asyncio.to_thread(
                    _search_by_content, directory, query, max_results
                )
            else:
                results = await asyncio.to_thread(
                    _search_by_name, directory, query, max_results
                )

            summary = f"Found {len(results)} result(s) for '{query}' in {directory}"
            return ToolResult(
                success=True,
                data={"results": results, "summary": summary},
                metadata={
                    "query": query,
                    "directory": directory,
                    "mode": mode,
                    "count": len(results),
                },
            )

        except Exception as exc:
            logger.error("LocalSearchTool failed: %s", exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))
