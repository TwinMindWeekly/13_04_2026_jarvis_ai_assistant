"""Job search adapters — one module per source.

Every source exposes ``async def fetch(query, location, limit) -> list[dict]``
where each dict follows this shape:

    {
        "source": str,           # e.g. "remoteok"
        "url": str,              # canonical job URL
        "title": str,
        "company": str,
        "location": str,
        "description": str,      # short; truncated if the source returns long HTML
        "salary": str,
        "remote": bool,
        "posted_at": str,        # ISO 8601 if available, else ""
    }

Sources MUST catch every network/parsing exception and return ``[]`` — the
scheduler iterates every source and should not be blocked by a single
flaky site.
"""

from app.services.job_sources.duckduckgo import fetch as fetch_duckduckgo
from app.services.job_sources.itviec import fetch as fetch_itviec
from app.services.job_sources.remoteok import fetch as fetch_remoteok
from app.services.job_sources.topcv import fetch as fetch_topcv
from app.services.job_sources.vietnamworks import fetch as fetch_vietnamworks
from app.services.job_sources.weworkremotely import fetch as fetch_weworkremotely

ALL_SOURCES = {
    "duckduckgo": fetch_duckduckgo,
    "topcv": fetch_topcv,
    "itviec": fetch_itviec,
    "vietnamworks": fetch_vietnamworks,
    "remoteok": fetch_remoteok,
    "weworkremotely": fetch_weworkremotely,
}


__all__ = [
    "ALL_SOURCES",
    "fetch_duckduckgo",
    "fetch_itviec",
    "fetch_remoteok",
    "fetch_topcv",
    "fetch_vietnamworks",
    "fetch_weworkremotely",
]
