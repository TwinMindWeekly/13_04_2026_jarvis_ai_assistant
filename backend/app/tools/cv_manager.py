"""cv_manager tool — agent access to CVs/portfolios (Phase 19)."""

from __future__ import annotations

import logging
from pathlib import Path

from app.db.connection import session_scope
from app.db.models import Job
from app.db.services.cvs import (
    clone_cv,
    cv_to_dict,
    get_cv,
    get_default_cv,
    list_cvs,
    set_pdf_file,
)
from app.models.cv_schemas import CVSections
from app.services.cv_renderer import render_html, render_pdf
from app.services.cv_tailor import tailor_cv
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class CVManagerTool(BaseTool):
    name = "cv_manager"
    description = (
        "Manage the user's CVs and portfolios. Actions: "
        "list (all CVs, optionally filter by kind='cv'|'portfolio'), "
        "get (one CV by id), "
        "tailor_for_job (clone a CV + rewrite via LLM for a specific job id — default CV used if cv_id omitted), "
        "export_pdf (render a CV to PDF on disk; returns the download_url), "
        "create_from_job (combo: tailor default CV for a job + export PDF). "
        "Use this when the user asks to prepare a CV for a company, customise a résumé, or download a PDF of their CV."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "get", "tailor_for_job", "export_pdf", "create_from_job"],
                "description": "What to do.",
            },
            "cv_id": {"type": "string", "description": "CV id (optional — default CV if omitted).", "default": None},
            "job_id": {"type": "integer", "description": "Job id (for tailor/create_from_job).", "default": None},
            "kind": {"type": "string", "description": "Filter list by 'cv' or 'portfolio'.", "default": None},
            "new_title": {"type": "string", "description": "Override title for the tailored CV.", "default": None},
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs) -> ToolResult:  # type: ignore[override]
        action = (kwargs.get("action") or "").lower()
        try:
            if action == "list":
                return await self._list(kwargs.get("kind"))
            if action == "get":
                return await self._get(kwargs.get("cv_id"))
            if action == "tailor_for_job":
                return await self._tailor(kwargs.get("cv_id"), kwargs.get("job_id"), kwargs.get("new_title"))
            if action == "export_pdf":
                return await self._export(kwargs.get("cv_id"))
            if action == "create_from_job":
                return await self._create_from_job(kwargs.get("job_id"), kwargs.get("new_title"))
            return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as exc:
            logger.exception("cv_manager failed (action=%s): %s", action, exc)
            return ToolResult(success=False, error=f"cv_manager error: {exc}")

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _list(self, kind: str | None) -> ToolResult:
        async with session_scope() as session:
            rows = await list_cvs(session, kind=kind)
            data = [cv_to_dict(c) for c in rows]
        # Strip heavy sections from the tool response — keep metadata only.
        slim = [
            {
                "id": c["id"],
                "title": c["title"],
                "kind": c["kind"],
                "template": c["template"],
                "is_default": c["is_default"],
                "tailored_for_job_id": c["tailored_for_job_id"],
                "pdf_file": c["pdf_file"],
                "updated_at": c["updated_at"],
            }
            for c in data
        ]
        return ToolResult(success=True, data={"count": len(slim), "cvs": slim})

    async def _get(self, cv_id: str | None) -> ToolResult:
        async with session_scope() as session:
            cv = await self._resolve(session, cv_id)
            if not cv:
                return ToolResult(success=False, error="No CV found (and no default configured).")
            return ToolResult(success=True, data=cv_to_dict(cv))

    async def _tailor(
        self, cv_id: str | None, job_id, new_title: str | None
    ) -> ToolResult:
        if job_id is None:
            return ToolResult(success=False, error="job_id is required for tailor_for_job.")
        async with session_scope() as session:
            src = await self._resolve(session, cv_id)
            if not src:
                return ToolResult(success=False, error="No source CV (set a default or pass cv_id).")
            job = await session.get(Job, int(job_id))
            if not job:
                return ToolResult(success=False, error=f"Job {job_id} not found.")
            sections = CVSections.model_validate_json(src.sections_json or "{}")
            job_dict = {
                "title": job.title or "",
                "company": job.company or "",
                "location": job.location or "",
                "description": job.description or "",
            }
            new_sections, rationale = await tailor_cv(sections, job_dict)
            suffix = job.company or job.title or f"Job #{job.id}"
            cloned = await clone_cv(
                session,
                src.id,
                new_title=(new_title or f"{src.title} — {suffix}"),
                job_id=job.id,
                sections_override=new_sections,
            )
        if not cloned:
            return ToolResult(success=False, error="Clone failed.")
        data = cv_to_dict(cloned)
        data["rationale"] = rationale
        return ToolResult(success=True, data=data)

    async def _export(self, cv_id: str | None) -> ToolResult:
        async with session_scope() as session:
            cv = await self._resolve(session, cv_id)
            if not cv:
                return ToolResult(success=False, error="No CV found.")
            cv_dict = cv_to_dict(cv)
            sections = CVSections.model_validate(cv_dict["sections"])
            template = cv.template
            title = cv.title
            target_id = cv.id
        html = render_html(sections, template=template, title=title)
        from app.core.config import settings  # noqa: PLC0415

        out_path = Path(settings.upload_dir) / "cvs" / f"{target_id}.pdf"
        await render_pdf(html, out_path)
        async with session_scope() as session:
            await set_pdf_file(session, target_id, str(out_path))
        return ToolResult(
            success=True,
            data={
                "id": target_id,
                "pdf_file": str(out_path),
                "download_url": f"/api/cvs/{target_id}/pdf",
            },
        )

    async def _create_from_job(self, job_id, new_title: str | None) -> ToolResult:
        tailored = await self._tailor(None, job_id, new_title)
        if not tailored.success:
            return tailored
        new_id = tailored.data.get("id") if isinstance(tailored.data, dict) else None
        if not new_id:
            return tailored
        exported = await self._export(new_id)
        if exported.success and isinstance(exported.data, dict):
            tailored.data["pdf_file"] = exported.data.get("pdf_file")
            tailored.data["download_url"] = exported.data.get("download_url")
        return tailored

    # ------------------------------------------------------------------

    @staticmethod
    async def _resolve(session, cv_id: str | None):
        if cv_id:
            return await get_cv(session, cv_id)
        return await get_default_cv(session, kind="cv")
