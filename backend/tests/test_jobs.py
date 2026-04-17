"""Unit tests for job matcher + jobs service + profile service."""

from __future__ import annotations

import asyncio

from app.services.jobs_matcher import score_job


def test_score_job_empty_profile():
    assert score_job({"title": "Senior Python"}, None) == 0.0
    assert score_job({"title": "Senior Python"}, {}) == 0.0


def test_score_job_full_match():
    profile = {
        "skills": ["python", "fastapi", "sqlalchemy"],
        "preferred_titles": ["senior python engineer"],
        "preferred_locations": ["hanoi"],
        "preferred_remote": True,
    }
    job = {
        "title": "Senior Python Engineer — FastAPI",
        "description": "We use Python, FastAPI, and SQLAlchemy for our data platform.",
        "company": "Acme",
        "location": "Hanoi, Vietnam",
        "remote": True,
    }
    score = score_job(job, profile)
    assert score > 0.15


def test_score_job_no_overlap():
    profile = {"skills": ["ruby"], "preferred_titles": ["rails developer"]}
    job = {"title": "Frontend React Engineer", "description": "React, Redux"}
    assert score_job(job, profile) == 0.0


def test_upsert_profile_roundtrip(temp_db):
    from app.db.connection import session_scope
    from app.db.services.user_profile import profile_to_dict, upsert_profile

    async def _run():
        async with session_scope() as session:
            await upsert_profile(
                session,
                full_name="Thanh Nhan",
                skills=["Python", "FastAPI"],
                preferred_titles=["Senior Python Engineer"],
                preferred_locations=["Hanoi"],
                preferred_remote=True,
            )
        async with session_scope() as session:
            # Update via upsert again — should not duplicate the row.
            await upsert_profile(session, headline="10+ years backend")
        async with session_scope() as session:
            from app.db.services.user_profile import get_profile  # noqa: PLC0415
            p = await get_profile(session)
            return profile_to_dict(p)

    data = asyncio.run(_run())
    assert data["full_name"] == "Thanh Nhan"
    assert data["headline"] == "10+ years backend"
    assert data["skills"] == ["Python", "FastAPI"]
    assert data["preferred_remote"] is True


def test_saved_search_crud(temp_db):
    from app.db.connection import session_scope
    from app.db.services.jobs import (
        create_saved_search,
        delete_saved_search,
        list_saved_searches,
    )

    async def _run():
        async with session_scope() as session:
            a = await create_saved_search(session, query="Python", location="Remote", sources=["remoteok"])
            await create_saved_search(session, query="Go", location="")
            rows_before = await list_saved_searches(session)
            await delete_saved_search(session, a.id)
            rows_after = await list_saved_searches(session)
            return len(rows_before), len(rows_after)

    before, after = asyncio.run(_run())
    assert before == 2
    assert after == 1


def test_refresh_from_profile_defaults_no_profile(temp_db):
    """With no profile, refresh still succeeds but inserts nothing (no titles)."""
    from app.db.connection import session_scope
    from app.db.services.jobs import refresh_from_profile_defaults

    async def _run():
        async with session_scope() as session:
            return await refresh_from_profile_defaults(session)

    result = asyncio.run(_run())
    assert result["inserted"] == 0
    assert result["discovered"] == 0
