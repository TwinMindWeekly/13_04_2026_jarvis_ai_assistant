"""RemoteOK public JSON API."""

from __future__ import annotations

import logging

from app.services.job_sources._common import build_client, truncate

logger = logging.getLogger(__name__)

SOURCE = "remoteok"
_API = "https://remoteok.com/api"


def _matches(entry: dict, query: str) -> bool:
    if not query:
        return True
    needle = query.lower()
    hay = " ".join(
        [
            str(entry.get("position") or ""),
            str(entry.get("company") or ""),
            " ".join(entry.get("tags") or []),
            str(entry.get("description") or ""),
        ]
    ).lower()
    return needle in hay


async def fetch(query: str, location: str = "", limit: int = 20) -> list[dict]:
    try:
        async with build_client() as client:
            resp = await client.get(_API)
            if resp.status_code != 200:
                logger.info("remoteok returned %d", resp.status_code)
                return []
            raw = resp.json()
    except Exception as exc:
        logger.warning("remoteok fetch failed: %s", exc)
        return []

    if not isinstance(raw, list):
        return []

    jobs: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("id"):
            continue  # skip the legal notice at index 0
        if not _matches(entry, query):
            continue
        url = entry.get("url") or entry.get("apply_url") or ""
        if not url:
            slug = entry.get("slug") or entry.get("id")
            url = f"https://remoteok.com/remote-jobs/{slug}"
        jobs.append(
            {
                "source": SOURCE,
                "url": url,
                "title": entry.get("position") or "",
                "company": entry.get("company") or "",
                "location": entry.get("location") or "Remote",
                "description": truncate(str(entry.get("description") or "")),
                "salary": (
                    f"{entry.get('salary_min')}-{entry.get('salary_max')}"
                    if entry.get("salary_min") else ""
                ),
                "remote": True,
                "posted_at": entry.get("date") or "",
            }
        )
        if len(jobs) >= limit:
            break
    return jobs
