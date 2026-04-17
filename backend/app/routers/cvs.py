"""CV / Portfolio API — CRUD, upload, PDF export, AI tailor (Phase 19)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.connection import get_session
from app.db.models import CV, Job
from app.db.services.cvs import (
    clone_cv,
    create_cv,
    cv_to_dict,
    delete_cv,
    get_cv,
    list_cvs,
    set_pdf_file,
    set_source_file,
    update_cv,
)
from app.models.cv_schemas import (
    CVCreate,
    CVExportResponse,
    CVSections,
    CVTailorRequest,
    CVUpdate,
)
from app.rag.document_parser import DocumentParser
from app.services.cv_extractor import parse_to_sections
from app.services.cv_renderer import render_html, render_pdf
from app.services.cv_tailor import tailor_cv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cvs")


def _cv_dir() -> Path:
    p = Path(settings.upload_dir) / "cvs"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# List / detail / CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_cvs_endpoint(
    kind: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = await list_cvs(session, kind=kind)
    data = [cv_to_dict(c) for c in rows]
    return {"cvs": data, "total": len(data)}


@router.get("/{cv_id}")
async def get_cv_endpoint(cv_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    cv = await get_cv(session, cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail=f"CV '{cv_id}' not found.")
    return cv_to_dict(cv)


@router.post("")
async def create_cv_endpoint(
    body: CVCreate, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        cv = await create_cv(
            session,
            title=body.title,
            kind=body.kind,
            template=body.template,
            sections=body.sections,
            is_default=body.is_default,
        )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return cv_to_dict(cv)


@router.patch("/{cv_id}")
async def update_cv_endpoint(
    cv_id: str,
    body: CVUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        cv = await update_cv(
            session,
            cv_id,
            title=body.title,
            kind=body.kind,
            template=body.template,
            sections=body.sections,
            is_default=body.is_default,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not cv:
        raise HTTPException(status_code=404, detail=f"CV '{cv_id}' not found.")
    await session.commit()
    return cv_to_dict(cv)


@router.delete("/{cv_id}")
async def delete_cv_endpoint(
    cv_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    # Best-effort remove files.
    cv = await get_cv(session, cv_id)
    if cv:
        for fp in (cv.source_file, cv.pdf_file):
            if fp:
                try:
                    Path(fp).unlink(missing_ok=True)
                except Exception:
                    pass
    deleted = await delete_cv(session, cv_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"CV '{cv_id}' not found.")
    await session.commit()
    return {"id": cv_id, "deleted": True}


# ---------------------------------------------------------------------------
# Upload — parse a CV file and seed sections
# ---------------------------------------------------------------------------


@router.post("/upload")
async def upload_cv(
    file: UploadFile = File(...),
    kind: str = Form("cv"),
    title: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in DocumentParser.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported CV file type: '{ext}'. Supported: {sorted(DocumentParser.SUPPORTED_EXTENSIONS)}",
        )

    cvs_dir = _cv_dir()
    file_id = str(uuid.uuid4())
    cv_path = cvs_dir / f"{file_id}{ext}"
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

    sections_dict = await parse_to_sections(cv_text)
    sections = CVSections.model_validate(sections_dict)

    derived_title = (title or sections.contact.full_name or file.filename or "Uploaded CV").strip()
    try:
        cv = await create_cv(
            session,
            title=derived_title,
            kind=kind,
            template="portfolio_minimal" if kind == "portfolio" else "minimal",
            sections=sections,
            source_file=str(cv_path),
        )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(
        "CV uploaded '%s' → id=%s, %d skills, %d experience entries",
        file.filename,
        cv.id,
        len(sections.skills),
        len(sections.experience),
    )
    return cv_to_dict(cv)


# ---------------------------------------------------------------------------
# Export PDF
# ---------------------------------------------------------------------------


@router.post("/{cv_id}/export", response_model=CVExportResponse)
async def export_cv(
    cv_id: str, session: AsyncSession = Depends(get_session)
) -> CVExportResponse:
    cv = await get_cv(session, cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail=f"CV '{cv_id}' not found.")
    sections = CVSections.model_validate_json(cv.sections_json or "{}")
    html = render_html(sections, template=cv.template, title=cv.title)
    out_path = _cv_dir() / f"{cv.id}.pdf"
    try:
        await render_pdf(html, out_path)
    except Exception as exc:
        logger.exception("CV PDF render failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"PDF export failed: {exc}") from exc

    await set_pdf_file(session, cv.id, str(out_path))
    await session.commit()
    return CVExportResponse(
        id=cv.id,
        pdf_file=str(out_path),
        download_url=f"/api/cvs/{cv.id}/pdf",
    )


@router.get("/{cv_id}/pdf")
async def download_cv_pdf(
    cv_id: str, session: AsyncSession = Depends(get_session)
) -> FileResponse:
    cv = await get_cv(session, cv_id)
    if not cv or not cv.pdf_file:
        raise HTTPException(status_code=404, detail="PDF not exported yet — call POST /export first.")
    path = Path(cv.pdf_file)
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF file missing on disk — re-export.")
    filename = f"{cv.title or cv_id}.pdf".replace("/", "-")
    return FileResponse(path, media_type="application/pdf", filename=filename)


@router.get("/{cv_id}/preview.html")
async def preview_cv_html(
    cv_id: str, session: AsyncSession = Depends(get_session)
) -> FileResponse:
    """Render the CV as HTML for inline iframe preview."""
    from fastapi.responses import HTMLResponse  # noqa: PLC0415

    cv = await get_cv(session, cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail=f"CV '{cv_id}' not found.")
    sections = CVSections.model_validate_json(cv.sections_json or "{}")
    html = render_html(sections, template=cv.template, title=cv.title)
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Tailor for a specific job
# ---------------------------------------------------------------------------


@router.post("/{cv_id}/tailor")
async def tailor_cv_endpoint(
    cv_id: str,
    body: CVTailorRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    src = await get_cv(session, cv_id)
    if not src:
        raise HTTPException(status_code=404, detail=f"CV '{cv_id}' not found.")
    job = await session.get(Job, body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {body.job_id} not found.")

    sections = CVSections.model_validate_json(src.sections_json or "{}")
    job_dict = {
        "title": job.title or "",
        "company": job.company or "",
        "location": job.location or "",
        "description": job.description or "",
    }
    new_sections, rationale = await tailor_cv(sections, job_dict)

    suffix = job.company or job.title or f"Job #{job.id}"
    new_title = body.new_title or f"{src.title} — {suffix}"

    cloned = await clone_cv(
        session,
        src.id,
        new_title=new_title,
        job_id=job.id,
        sections_override=new_sections,
    )
    if not cloned:
        raise HTTPException(status_code=500, detail="Clone failed.")
    await session.commit()

    data = cv_to_dict(cloned)
    data["rationale"] = rationale
    return data
