"""CRUD + refresh helpers for the ``jobs`` and ``saved_job_searches`` tables."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, SavedJobSearch
from app.db.services.user_profile import profile_to_dict, get_profile
from app.services.job_sources import ALL_SOURCES
from app.services.jobs_matcher import score_job

logger = logging.getLogger(__name__)


def job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "source": job.source,
        "url": job.url,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description,
        "salary": job.salary,
        "remote": bool(job.remote),
        "posted_at": job.posted_at,
        "match_score": float(job.match_score or 0.0),
        "saved": bool(job.saved),
        "fetched_at": job.fetched_at.isoformat() if job.fetched_at else "",
    }


def saved_search_to_dict(s: SavedJobSearch) -> dict:
    try:
        sources = json.loads(s.sources) if s.sources else []
    except Exception:
        sources = []
    return {
        "id": s.id,
        "query": s.query,
        "location": s.location,
        "sources": sources,
        "enabled": bool(s.enabled),
        "created_at": s.created_at.isoformat() if s.created_at else "",
    }


# ---------------------------------------------------------------------------
# Jobs — read/list
# ---------------------------------------------------------------------------


async def list_jobs(
    session: AsyncSession,
    *,
    source: str | None = None,
    min_score: float | None = None,
    saved_only: bool = False,
    limit: int = 100,
) -> list[Job]:
    stmt = select(Job).order_by(desc(Job.match_score), desc(Job.fetched_at)).limit(limit)
    if source:
        stmt = stmt.where(Job.source == source)
    if min_score is not None:
        stmt = stmt.where(Job.match_score >= min_score)
    if saved_only:
        stmt = stmt.where(Job.saved.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def set_job_saved(session: AsyncSession, job_id: int, saved: bool) -> Job | None:
    job = await session.get(Job, job_id)
    if not job:
        return None
    job.saved = bool(saved)
    await session.flush()
    return job


# ---------------------------------------------------------------------------
# Saved searches
# ---------------------------------------------------------------------------


async def list_saved_searches(session: AsyncSession) -> list[SavedJobSearch]:
    rows = await session.execute(select(SavedJobSearch).order_by(SavedJobSearch.id))
    return list(rows.scalars().all())


async def create_saved_search(
    session: AsyncSession,
    *,
    query: str,
    location: str = "",
    sources: list[str] | None = None,
    enabled: bool = True,
) -> SavedJobSearch:
    row = SavedJobSearch(
        query=query.strip(),
        location=location.strip(),
        sources=json.dumps(sources or []),
        enabled=bool(enabled),
    )
    session.add(row)
    await session.flush()
    return row


async def delete_saved_search(session: AsyncSession, search_id: int) -> bool:
    row = await session.get(SavedJobSearch, search_id)
    if not row:
        return False
    await session.delete(row)
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Refresh — run all active saved searches across all sources.
# ---------------------------------------------------------------------------


def _dedupe_key(job: dict) -> tuple[str, str]:
    return (job.get("source", ""), (job.get("url") or "").strip())


async def _run_sources(
    query: str,
    location: str,
    selected: Iterable[str] | None,
    limit_per_source: int,
) -> list[dict]:
    jobs: list[dict] = []
    names = list(selected) if selected else list(ALL_SOURCES.keys())
    for name in names:
        fn = ALL_SOURCES.get(name)
        if fn is None:
            continue
        try:
            rows = await fn(query, location, limit_per_source)
        except Exception as exc:
            logger.warning("Job source '%s' raised: %s", name, exc)
            rows = []
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict) or not r.get("url") or not r.get("title"):
                continue
            r.setdefault("source", name)
            jobs.append(r)
    return jobs


async def refresh_jobs(session: AsyncSession, *, limit_per_source: int = 20) -> dict:
    """Execute every enabled saved search against every source, upsert rows."""
    searches = await list_saved_searches(session)
    profile = await get_profile(session)
    profile_dict = profile_to_dict(profile)

    discovered: dict[tuple[str, str], dict] = {}
    ran: list[dict] = []
    for s in searches:
        if not s.enabled:
            continue
        try:
            sources = json.loads(s.sources) if s.sources else []
        except Exception:
            sources = []
        rows = await _run_sources(s.query, s.location, sources, limit_per_source)
        ran.append({"query": s.query, "location": s.location, "fetched": len(rows)})
        for r in rows:
            key = _dedupe_key(r)
            if key[1]:
                discovered[key] = r

    inserted = 0
    updated = 0
    now = datetime.now(timezone.utc)

    for (source, url), data in discovered.items():
        existing = (
            await session.execute(
                select(Job).where(Job.source == source, Job.url == url).limit(1)
            )
        ).scalars().first()
        score = score_job(data, profile_dict)
        if existing:
            existing.title = data.get("title") or existing.title
            existing.company = data.get("company") or existing.company
            existing.location = data.get("location") or existing.location
            existing.description = data.get("description") or existing.description
            existing.salary = data.get("salary") or existing.salary
            existing.remote = bool(data.get("remote"))
            existing.posted_at = data.get("posted_at") or existing.posted_at
            existing.match_score = score
            existing.fetched_at = now
            updated += 1
        else:
            session.add(
                Job(
                    source=source,
                    url=url,
                    title=data.get("title", ""),
                    company=data.get("company", ""),
                    location=data.get("location", ""),
                    description=data.get("description", ""),
                    salary=data.get("salary", ""),
                    remote=bool(data.get("remote")),
                    posted_at=data.get("posted_at", ""),
                    match_score=score,
                    fetched_at=now,
                )
            )
            inserted += 1

    await session.flush()
    return {"inserted": inserted, "updated": updated, "searches": ran}


async def refresh_from_profile_defaults(
    session: AsyncSession,
    *,
    limit_per_source: int = 10,
) -> dict:
    """Run a refresh using the user's preferred_titles + locations only.

    Useful for first-time use when no saved search exists yet.
    """
    profile = await get_profile(session)
    profile_dict = profile_to_dict(profile)
    titles = profile_dict.get("preferred_titles") or []
    locations = profile_dict.get("preferred_locations") or [""]

    discovered: dict[tuple[str, str], dict] = {}
    for title in titles[:3]:
        for loc in locations[:2]:
            rows = await _run_sources(title, loc, None, limit_per_source)
            for r in rows:
                key = _dedupe_key(r)
                if key[1]:
                    discovered[key] = r

    inserted = 0
    now = datetime.now(timezone.utc)
    for (source, url), data in discovered.items():
        existing = (
            await session.execute(
                select(Job).where(Job.source == source, Job.url == url).limit(1)
            )
        ).scalars().first()
        score = score_job(data, profile_dict)
        if existing:
            existing.match_score = score
            existing.fetched_at = now
            continue
        session.add(
            Job(
                source=source,
                url=url,
                title=data.get("title", ""),
                company=data.get("company", ""),
                location=data.get("location", ""),
                description=data.get("description", ""),
                salary=data.get("salary", ""),
                remote=bool(data.get("remote")),
                posted_at=data.get("posted_at", ""),
                match_score=score,
                fetched_at=now,
            )
        )
        inserted += 1
    await session.flush()
    return {"inserted": inserted, "discovered": len(discovered)}


async def purge_old_jobs(session: AsyncSession, *, keep: int = 500) -> int:
    """Delete the oldest non-saved jobs when the table grows past ``keep`` rows."""
    total = (await session.execute(select(Job))).scalars().all()
    if len(total) <= keep:
        return 0
    ids = [j.id for j in sorted(total, key=lambda j: j.fetched_at or datetime.min) if not j.saved]
    extra = len(total) - keep
    target_ids = ids[: extra]
    if not target_ids:
        return 0
    await session.execute(delete(Job).where(Job.id.in_(target_ids)))
    return len(target_ids)
