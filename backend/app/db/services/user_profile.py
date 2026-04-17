"""CRUD helpers for the singleton ``UserProfile`` row."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserProfile

logger = logging.getLogger(__name__)


def _json_load(raw: str, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def profile_to_dict(profile: UserProfile | None) -> dict:
    if profile is None:
        return {
            "id": None,
            "full_name": "",
            "headline": "",
            "summary": "",
            "skills": [],
            "preferred_titles": [],
            "preferred_locations": [],
            "preferred_remote": False,
            "cv_path": "",
            "cv_text": "",
            "updated_at": None,
        }
    return {
        "id": profile.id,
        "full_name": profile.full_name,
        "headline": profile.headline,
        "summary": profile.summary,
        "skills": _json_load(profile.skills, []),
        "preferred_titles": _json_load(profile.preferred_titles, []),
        "preferred_locations": _json_load(profile.preferred_locations, []),
        "preferred_remote": bool(profile.preferred_remote),
        "cv_path": profile.cv_path,
        "cv_text": profile.cv_text,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


async def get_profile(session: AsyncSession) -> UserProfile | None:
    rows = await session.execute(select(UserProfile).limit(1))
    return rows.scalars().first()


async def upsert_profile(
    session: AsyncSession,
    **fields,
) -> UserProfile:
    """Create or update the singleton profile row.

    List fields (skills/preferred_titles/preferred_locations) may be passed
    as Python lists; they are serialised to JSON before persisting.
    """
    profile = await get_profile(session)
    if profile is None:
        profile = UserProfile()
        session.add(profile)
    for key, value in fields.items():
        if value is None:
            continue
        if key in {"skills", "preferred_titles", "preferred_locations"}:
            if isinstance(value, list):
                setattr(profile, key, json.dumps(value, ensure_ascii=False))
            else:
                setattr(profile, key, str(value))
        elif key == "preferred_remote":
            profile.preferred_remote = bool(value)
        elif hasattr(profile, key):
            setattr(profile, key, value)
    profile.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return profile
