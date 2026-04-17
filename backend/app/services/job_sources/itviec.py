"""ITviec public job search scraper (best-effort)."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from app.services.job_sources._common import build_client, truncate

logger = logging.getLogger(__name__)

SOURCE = "itviec"
_BASE = "https://itviec.com/it-jobs"


async def fetch(query: str, location: str = "", limit: int = 20) -> list[dict]:
    params = {}
    if query:
        params["keywords"] = query
    if location:
        params["city"] = location

    try:
        async with build_client() as client:
            resp = await client.get(_BASE, params=params)
            if resp.status_code != 200:
                return []
            html = resp.text
    except Exception as exc:
        logger.warning("itviec fetch failed: %s", exc)
        return []

    try:
        from selectolax.parser import HTMLParser  # noqa: PLC0415
    except ImportError:
        return []

    jobs: list[dict] = []
    try:
        tree = HTMLParser(html)
        for card in tree.css("[data-controller*='job']")[:limit * 2]:
            title_el = card.css_first("h3 a, a.ga_jobSearch_jobTitle, h3")
            company_el = card.css_first(".company, .employer, a.company-name")
            loc_el = card.css_first(".city, .location")
            salary_el = card.css_first(".salary, .salary_label")
            if not title_el:
                continue
            href = (title_el.attributes.get("href") or "").strip() if hasattr(title_el, "attributes") else ""
            if href and href.startswith("/"):
                href = f"https://itviec.com{href}"
            title = title_el.text(strip=True)
            jobs.append(
                {
                    "source": SOURCE,
                    "url": href or _BASE + "?" + "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items()),
                    "title": title,
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
        logger.warning("itviec parse failed: %s", exc)
        return []
    return jobs
