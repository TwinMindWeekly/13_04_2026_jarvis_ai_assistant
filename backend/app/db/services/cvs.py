"""CRUD helpers for the ``cvs`` table (Phase 19)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CV
from app.models.cv_schemas import CVSections

logger = logging.getLogger(__name__)

ALLOWED_KINDS = {"cv", "portfolio"}
ALLOWED_TEMPLATES = {"minimal", "modern", "portfolio_minimal"}


def _sections_from_json(raw: str) -> CVSections:
    if not raw:
        return CVSections()
    try:
        return CVSections.model_validate(json.loads(raw))
    except Exception as exc:
        logger.warning("CV sections JSON invalid — returning empty: %s", exc)
        return CVSections()


def cv_to_dict(cv: CV) -> dict:
    return {
        "id": cv.id,
        "title": cv.title,
        "kind": cv.kind,
        "template": cv.template,
        "sections": _sections_from_json(cv.sections_json).model_dump(),
        "source_file": cv.source_file or "",
        "pdf_file": cv.pdf_file or "",
        "tailored_from_cv_id": cv.tailored_from_cv_id,
        "tailored_for_job_id": cv.tailored_for_job_id,
        "is_default": bool(cv.is_default),
        "created_at": cv.created_at.isoformat() if cv.created_at else None,
        "updated_at": cv.updated_at.isoformat() if cv.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


async def list_cvs(session: AsyncSession, kind: str | None = None) -> list[CV]:
    stmt = select(CV).order_by(CV.is_default.desc(), CV.updated_at.desc())
    if kind:
        stmt = stmt.where(CV.kind == kind)
    return list((await session.execute(stmt)).scalars().all())


async def get_cv(session: AsyncSession, cv_id: str) -> CV | None:
    return await session.get(CV, cv_id)


async def get_default_cv(session: AsyncSession, kind: str = "cv") -> CV | None:
    rows = await session.execute(
        select(CV).where(CV.kind == kind, CV.is_default.is_(True)).limit(1)
    )
    cv = rows.scalars().first()
    if cv:
        return cv
    rows = await session.execute(
        select(CV).where(CV.kind == kind).order_by(CV.updated_at.desc()).limit(1)
    )
    return rows.scalars().first()


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


async def _ensure_single_default(session: AsyncSession, cv_id: str, kind: str) -> None:
    rows = await session.execute(select(CV).where(CV.kind == kind))
    for other in rows.scalars().all():
        other.is_default = other.id == cv_id


def _normalise_sections(sections: CVSections | dict | None) -> str:
    if sections is None:
        payload = CVSections().model_dump()
    elif isinstance(sections, CVSections):
        payload = sections.model_dump()
    else:
        payload = CVSections.model_validate(sections).model_dump()
    return json.dumps(payload, ensure_ascii=False)


async def create_cv(
    session: AsyncSession,
    *,
    title: str,
    kind: str = "cv",
    template: str = "minimal",
    sections: CVSections | dict | None = None,
    source_file: str = "",
    is_default: bool = False,
    tailored_from_cv_id: str | None = None,
    tailored_for_job_id: int | None = None,
) -> CV:
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"Unsupported CV kind: {kind}")
    if template not in ALLOWED_TEMPLATES:
        raise ValueError(f"Unsupported CV template: {template}")

    cv = CV(
        id=str(uuid.uuid4()),
        title=title.strip() or "Untitled CV",
        kind=kind,
        template=template,
        sections_json=_normalise_sections(sections),
        source_file=source_file,
        is_default=bool(is_default),
        tailored_from_cv_id=tailored_from_cv_id,
        tailored_for_job_id=tailored_for_job_id,
    )
    session.add(cv)
    await session.flush()

    # First CV of its kind auto-becomes default.
    total_of_kind = (
        await session.execute(select(CV).where(CV.kind == kind))
    ).scalars().all()
    if is_default or len(total_of_kind) == 1:
        await _ensure_single_default(session, cv.id, kind)

    await session.flush()
    return cv


async def update_cv(
    session: AsyncSession,
    cv_id: str,
    *,
    title: str | None = None,
    kind: str | None = None,
    template: str | None = None,
    sections: CVSections | dict | None = None,
    is_default: bool | None = None,
) -> CV | None:
    cv = await session.get(CV, cv_id)
    if not cv:
        return None
    if title is not None and title.strip():
        cv.title = title.strip()
    if kind is not None:
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"Unsupported CV kind: {kind}")
        cv.kind = kind
    if template is not None:
        if template not in ALLOWED_TEMPLATES:
            raise ValueError(f"Unsupported CV template: {template}")
        cv.template = template
    if sections is not None:
        cv.sections_json = _normalise_sections(sections)
    if is_default is not None:
        if bool(is_default):
            await _ensure_single_default(session, cv.id, cv.kind)
        else:
            cv.is_default = False
    cv.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return cv


async def delete_cv(session: AsyncSession, cv_id: str) -> bool:
    cv = await session.get(CV, cv_id)
    if not cv:
        return False
    was_default = cv.is_default
    kind = cv.kind
    await session.delete(cv)
    await session.flush()
    if was_default:
        rows = await session.execute(
            select(CV).where(CV.kind == kind).order_by(CV.updated_at.desc()).limit(1)
        )
        fallback = rows.scalars().first()
        if fallback:
            fallback.is_default = True
            await session.flush()
    return True


async def clone_cv(
    session: AsyncSession,
    source_id: str,
    *,
    new_title: str | None = None,
    job_id: int | None = None,
    sections_override: CVSections | None = None,
) -> CV | None:
    """Duplicate an existing CV — used by the tailor flow."""
    src = await session.get(CV, source_id)
    if not src:
        return None
    sections = sections_override if sections_override is not None else _sections_from_json(src.sections_json)
    clone_title = new_title or f"{src.title} — clone"
    return await create_cv(
        session,
        title=clone_title,
        kind=src.kind,
        template=src.template,
        sections=sections,
        source_file="",
        is_default=False,
        tailored_from_cv_id=src.id,
        tailored_for_job_id=job_id,
    )


async def set_source_file(session: AsyncSession, cv_id: str, path: str) -> None:
    cv = await session.get(CV, cv_id)
    if not cv:
        return
    cv.source_file = path
    cv.updated_at = datetime.now(timezone.utc)
    await session.flush()


async def set_pdf_file(session: AsyncSession, cv_id: str, path: str) -> None:
    cv = await session.get(CV, cv_id)
    if not cv:
        return
    cv.pdf_file = path
    cv.updated_at = datetime.now(timezone.utc)
    await session.flush()
