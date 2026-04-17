"""DuckDuckGo-backed job search using the ``ddgs`` lib.

Turns ``query="Senior Python"`` + ``location="Remote"`` into a DuckDuckGo
query and returns the result URLs as "job-shaped" dicts. DuckDuckGo does
not know which results are actually job postings, so the caller should
treat every entry as a lead the user still has to vet.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

SOURCE = "duckduckgo"


def _search_sync(query: str, limit: int) -> list[dict]:
    try:
        from ddgs import DDGS  # noqa: PLC0415
    except ImportError:
        logger.warning("ddgs not installed — duckduckgo job source disabled")
        return []

    rows: list[dict] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=limit):
                rows.append(r)
    except Exception as exc:
        logger.warning("duckduckgo search failed: %s", exc)
    return rows


async def fetch(query: str, location: str = "", limit: int = 20) -> list[dict]:
    q = f"{query} jobs"
    if location:
        q += f" {location}"
    rows = await asyncio.to_thread(_search_sync, q, limit)
    results: list[dict] = []
    for r in rows:
        url = r.get("href") or r.get("url") or ""
        if not url:
            continue
        results.append(
            {
                "source": SOURCE,
                "url": url,
                "title": r.get("title", "") or "",
                "company": "",
                "location": location,
                "description": (r.get("body", "") or r.get("description", ""))[:500],
                "salary": "",
                "remote": "remote" in q.lower(),
                "posted_at": "",
            }
        )
    return results
