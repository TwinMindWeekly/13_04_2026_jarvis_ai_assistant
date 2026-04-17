"""User profile API — read, edit, and seed from an uploaded CV."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.connection import get_session
from app.db.services.user_profile import get_profile, profile_to_dict, upsert_profile
from app.rag.document_parser import DocumentParser
from app.services.cv_extractor import extract_profile_fields

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile")


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    headline: str | None = None
    summary: str | None = None
    skills: list[str] | None = None
    preferred_titles: list[str] | None = None
    preferred_locations: list[str] | None = None
    preferred_remote: bool | None = None


@router.get("")
async def get_profile_endpoint(session: AsyncSession = Depends(get_session)) -> dict:
    profile = await get_profile(session)
    return profile_to_dict(profile)


@router.put("")
async def update_profile_endpoint(
    body: ProfileUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    payload = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    profile = await upsert_profile(session, **payload)
    await session.commit()
    return profile_to_dict(profile)


@router.post("/upload")
async def upload_cv(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Upload a CV (PDF/DOCX/TXT/MD), extract fields via LLM, seed the profile."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in DocumentParser.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported CV file type: '{ext}'. Supported: {sorted(DocumentParser.SUPPORTED_EXTENSIONS)}",
        )

    # Persist CV under uploads/profile/{uuid}{ext}
    cv_dir = Path(settings.upload_dir) / "profile"
    cv_dir.mkdir(parents=True, exist_ok=True)
    cv_path = cv_dir / f"{uuid.uuid4()}{ext}"
    content = await file.read()
    cv_path.write_bytes(content)

    parser = DocumentParser()
    try:
        chunks = await parser.parse_file(str(cv_path))
    except Exception as exc:
        cv_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Could not parse CV: {exc}") from exc

    cv_text = "\n\n".join(c.get("content", "") for c in chunks).strip()
    if not cv_text:
        cv_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="CV parse returned no text.")

    extracted = await extract_profile_fields(cv_text)

    profile = await upsert_profile(
        session,
        full_name=extracted.get("full_name") or None,
        headline=extracted.get("headline") or None,
        skills=extracted.get("skills") or [],
        preferred_titles=extracted.get("preferred_titles") or [],
        preferred_locations=extracted.get("preferred_locations") or [],
        preferred_remote=extracted.get("preferred_remote"),
        cv_path=str(cv_path),
        cv_text=cv_text[:20000],
    )
    await session.commit()

    logger.info(
        "Profile seeded from CV '%s' — %d skills, %d titles",
        file.filename,
        len(extracted.get("skills", [])),
        len(extracted.get("preferred_titles", [])),
    )
    return profile_to_dict(profile)
