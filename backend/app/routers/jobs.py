"""Jobs API — list, refresh, save, and manage saved searches."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.db.services.jobs import (
    create_saved_search,
    delete_saved_search,
    job_to_dict,
    list_jobs,
    list_saved_searches,
    purge_old_jobs,
    refresh_from_profile_defaults,
    refresh_jobs,
    saved_search_to_dict,
    set_job_saved,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs")


class SavedSearchCreate(BaseModel):
    query: str
    location: str = ""
    sources: list[str] | None = None
    enabled: bool = True


@router.get("")
async def list_jobs_endpoint(
    source: str | None = Query(None),
    min_score: float | None = Query(None),
    saved_only: bool = Query(False),
    limit: int = Query(100),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = await list_jobs(
        session,
        source=source,
        min_score=min_score,
        saved_only=saved_only,
        limit=limit,
    )
    return {"jobs": [job_to_dict(r) for r in rows], "count": len(rows)}


@router.post("/refresh")
async def refresh_endpoint(session: AsyncSession = Depends(get_session)) -> dict:
    saved = await list_saved_searches(session)
    if saved:
        result = await refresh_jobs(session)
    else:
        result = await refresh_from_profile_defaults(session)
    # Keep jobs table from unbounded growth.
    purged = await purge_old_jobs(session)
    await session.commit()
    return {**result, "purged": purged}


@router.post("/{job_id}/save")
async def save_job_endpoint(
    job_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await set_job_saved(session, job_id, True)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    await session.commit()
    return job_to_dict(job)


@router.delete("/{job_id}/save")
async def unsave_job_endpoint(
    job_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await set_job_saved(session, job_id, False)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    await session.commit()
    return job_to_dict(job)


@router.get("/saved-searches")
async def list_saved_searches_endpoint(
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = await list_saved_searches(session)
    return {"searches": [saved_search_to_dict(r) for r in rows], "count": len(rows)}


@router.post("/saved-searches")
async def create_saved_search_endpoint(
    body: SavedSearchCreate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query is required.")
    row = await create_saved_search(
        session,
        query=body.query,
        location=body.location,
        sources=body.sources,
        enabled=body.enabled,
    )
    await session.commit()
    return saved_search_to_dict(row)


@router.delete("/saved-searches/{search_id}")
async def delete_saved_search_endpoint(
    search_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    deleted = await delete_saved_search(session, search_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Saved search {search_id} not found.")
    await session.commit()
    return {"id": search_id, "deleted": True}
