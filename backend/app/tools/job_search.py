"""job_search tool — agent access to the job board pipeline."""

from __future__ import annotations

import logging

from app.db.connection import session_scope
from app.db.services.jobs import (
    create_saved_search,
    job_to_dict,
    list_jobs,
    refresh_from_profile_defaults,
    refresh_jobs,
    set_job_saved,
)
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class JobSearchTool(BaseTool):
    name = "job_search"
    description = (
        "Search and track job postings matched against the user's profile. "
        "Actions: list_tracked (jobs already in the DB, sorted by match score), "
        "search (run a one-off search across all sources), "
        "refresh (re-run every active saved search — may take 10-30s), "
        "save (bookmark a job by id), "
        "unsave (remove bookmark). "
        "Match score 0..1 is Jaccard overlap between the user's skills/titles and the job's title+description, with small bonuses for matching location and remote preference."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_tracked", "search", "refresh", "save", "unsave"],
                "description": "What to do.",
            },
            "query": {
                "type": "string",
                "description": "Job title or keywords (for search).",
                "default": None,
            },
            "location": {
                "type": "string",
                "description": "City/region filter (for search).",
                "default": "",
            },
            "source": {
                "type": "string",
                "description": "Filter list_tracked by source (duckduckgo/topcv/itviec/vietnamworks/remoteok/weworkremotely).",
                "default": None,
            },
            "min_score": {
                "type": "number",
                "description": "Minimum match_score for list_tracked (0..1).",
                "default": None,
            },
            "saved_only": {
                "type": "boolean",
                "description": "list_tracked: only return saved jobs.",
                "default": False,
            },
            "job_id": {"type": "integer", "description": "Job id (save/unsave).", "default": None},
            "limit": {"type": "integer", "description": "Max rows.", "default": 25},
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs) -> ToolResult:  # type: ignore[override]
        action = (kwargs.get("action") or "").lower()
        try:
            if action == "list_tracked":
                return await self._list_tracked(kwargs)
            if action == "search":
                return await self._search(kwargs)
            if action == "refresh":
                return await self._refresh()
            if action == "save":
                return await self._toggle_save(kwargs.get("job_id"), True)
            if action == "unsave":
                return await self._toggle_save(kwargs.get("job_id"), False)
            return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as exc:
            logger.exception("job_search failed (%s): %s", action, exc)
            return ToolResult(success=False, error=f"job_search error: {exc}")

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _list_tracked(self, kw: dict) -> ToolResult:
        limit = int(kw.get("limit") or 25)
        async with session_scope() as session:
            rows = await list_jobs(
                session,
                source=kw.get("source"),
                min_score=(float(kw["min_score"]) if kw.get("min_score") is not None else None),
                saved_only=bool(kw.get("saved_only")),
                limit=limit,
            )
            items = [job_to_dict(j) for j in rows]
        return ToolResult(success=True, data={"count": len(items), "jobs": items})

    async def _search(self, kw: dict) -> ToolResult:
        query = (kw.get("query") or "").strip()
        if not query:
            return ToolResult(success=False, error="query is required for search.")
        location = (kw.get("location") or "").strip()
        limit = int(kw.get("limit") or 20)

        async with session_scope() as session:
            # Create a temporary saved-search row, refresh, then return fresh jobs.
            row = await create_saved_search(
                session,
                query=query,
                location=location,
                sources=None,
                enabled=True,
            )
            temp_id = row.id
        async with session_scope() as session:
            result = await refresh_jobs(session, limit_per_source=limit)
        async with session_scope() as session:
            rows = await list_jobs(session, limit=limit * 2)
            items = [job_to_dict(j) for j in rows if query.lower() in (j.title + " " + j.description).lower()][:limit]
            # Clean up the temporary saved-search.
            from app.db.services.jobs import delete_saved_search  # noqa: PLC0415
            await delete_saved_search(session, temp_id)

        return ToolResult(
            success=True,
            data={
                "query": query,
                "location": location,
                "count": len(items),
                "jobs": items,
                "refresh_stats": result,
            },
        )

    async def _refresh(self) -> ToolResult:
        async with session_scope() as session:
            from app.db.services.jobs import list_saved_searches  # noqa: PLC0415
            saved = await list_saved_searches(session)
            if saved:
                result = await refresh_jobs(session)
            else:
                result = await refresh_from_profile_defaults(session)
        return ToolResult(success=True, data=result)

    async def _toggle_save(self, job_id, saved: bool) -> ToolResult:
        if job_id is None:
            return ToolResult(success=False, error="job_id is required.")
        async with session_scope() as session:
            job = await set_job_saved(session, int(job_id), saved)
            if not job:
                return ToolResult(success=False, error=f"Job {job_id} not found.")
            data = job_to_dict(job)
        return ToolResult(success=True, data=data)
