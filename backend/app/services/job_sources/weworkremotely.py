"""WeWorkRemotely RSS feed ingest.

Parses the public all-jobs RSS and applies a best-effort keyword filter.
No HTML scraping — the feed is a stable contract. If the feed is blocked
or misformatted the adapter returns ``[]`` without raising.
"""

from __future__ import annotations

import logging
import re
from xml.etree import ElementTree as ET

from app.services.job_sources._common import build_client, truncate

logger = logging.getLogger(__name__)

SOURCE = "weworkremotely"
_FEED = "https://weworkremotely.com/remote-jobs.rss"


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


async def fetch(query: str, location: str = "", limit: int = 20) -> list[dict]:
    try:
        async with build_client() as client:
            resp = await client.get(_FEED)
            if resp.status_code != 200:
                return []
            xml = resp.text
    except Exception as exc:
        logger.warning("weworkremotely feed failed: %s", exc)
        return []

    try:
        root = ET.fromstring(xml)
    except Exception as exc:
        logger.warning("weworkremotely XML parse failed: %s", exc)
        return []

    needle = (query or "").lower().strip()
    jobs: list[dict] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        desc_raw = item.findtext("description") or ""
        pub = (item.findtext("pubDate") or "").strip()
        if not title or not url:
            continue
        hay = f"{title} {desc_raw}".lower()
        if needle and needle not in hay:
            continue
        # Title format is often "Company: Title".
        if ":" in title:
            company, _, role = title.partition(":")
            company, role = company.strip(), role.strip()
        else:
            company, role = "", title
        jobs.append(
            {
                "source": SOURCE,
                "url": url,
                "title": role,
                "company": company,
                "location": "Remote",
                "description": truncate(_strip_tags(desc_raw)),
                "salary": "",
                "remote": True,
                "posted_at": pub,
            }
        )
        if len(jobs) >= limit:
            break
    return jobs
