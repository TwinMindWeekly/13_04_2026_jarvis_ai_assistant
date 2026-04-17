"""TopCV.vn public job search scraper.

Public HTML — URL schema as of 2026-04 is ``/tim-viec-lam-<slug>``. If the
HTML changes, the adapter returns ``[]`` and logs a warning rather than
raising.
"""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from app.services.job_sources._common import build_client, truncate

logger = logging.getLogger(__name__)

SOURCE = "topcv"
_BASE = "https://www.topcv.vn/tim-viec-lam-"


async def fetch(query: str, location: str = "", limit: int = 20) -> list[dict]:
    if not query:
        return []
    slug = quote_plus(query.lower().replace(" ", "-"))
    url = f"{_BASE}{slug}"
    if location:
        url += f"-tai-{quote_plus(location.lower().replace(' ', '-'))}"
    url += ".html"

    try:
        async with build_client() as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            html = resp.text
    except Exception as exc:
        logger.warning("topcv fetch failed: %s", exc)
        return []

    try:
        from selectolax.parser import HTMLParser  # noqa: PLC0415
    except ImportError:
        return []

    jobs: list[dict] = []
    try:
        tree = HTMLParser(html)
        for card in tree.css(".job-item-2, .job-item, div[data-job-id]")[:limit * 2]:
            title_el = card.css_first(".title a, h3 a, a.job-title")
            company_el = card.css_first(".company a, .company-name, .company")
            loc_el = card.css_first(".address, .location")
            salary_el = card.css_first(".salary, .title-salary")
            if not title_el:
                continue
            href = (title_el.attributes.get("href") or "").strip()
            if not href:
                continue
            if href.startswith("/"):
                href = f"https://www.topcv.vn{href}"
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
        logger.warning("topcv parse failed: %s", exc)
        return []
    return jobs
