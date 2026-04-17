"""VietnamWorks public job search scraper (best-effort)."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from app.services.job_sources._common import build_client, truncate

logger = logging.getLogger(__name__)

SOURCE = "vietnamworks"
_BASE = "https://www.vietnamworks.com/viec-lam"


async def fetch(query: str, location: str = "", limit: int = 20) -> list[dict]:
    if not query:
        return []
    q = quote_plus(query)
    url = f"{_BASE}?q={q}"
    if location:
        url += f"&location={quote_plus(location)}"

    try:
        async with build_client() as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            html = resp.text
    except Exception as exc:
        logger.warning("vietnamworks fetch failed: %s", exc)
        return []

    try:
        from selectolax.parser import HTMLParser  # noqa: PLC0415
    except ImportError:
        return []

    jobs: list[dict] = []
    try:
        tree = HTMLParser(html)
        for card in tree.css("[data-job-id], .job-item, a[href*='-jv'][href*='.html']")[:limit * 2]:
            title_el = card.css_first("h4 a, h3 a, .job-title a, a[href*='-jv']")
            if not title_el:
                title_el = card if card.tag == "a" else None
            if not title_el:
                continue
            href = (title_el.attributes.get("href") or "").strip()
            if href and href.startswith("/"):
                href = f"https://www.vietnamworks.com{href}"
            if not href:
                continue
            company_el = card.css_first(".company a, .company-name, .employer")
            loc_el = card.css_first(".location, .city")
            salary_el = card.css_first(".salary")
            jobs.append(
                {
                    "source": SOURCE,
                    "url": href,
                    "title": title_el.text(strip=True),
                    "company": company_el.text(strip=True) if company_el else "",
                    "location": loc_el.text(strip=True) if loc_el else location,
                    "description": "",
                    "salary": truncate(salary_el.text(strip=True), 80) if salary_el else "",
                    "remote": False,
                    "posted_at": "",
                }
            )
            if len(jobs) >= limit:
                break
    except Exception as exc:
        logger.warning("vietnamworks parse failed: %s", exc)
        return []
    return jobs
