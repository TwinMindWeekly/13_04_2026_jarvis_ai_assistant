"""Phase 19 — CV CRUD, renderer, tailor, cv_manager tool."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Service CRUD
# ---------------------------------------------------------------------------


def test_create_cv_auto_default(temp_db):
    from app.db.connection import session_scope
    from app.db.services.cvs import create_cv, list_cvs

    async def _run():
        async with session_scope() as session:
            cv = await create_cv(session, title="My CV")
            rows = await list_cvs(session)
        return cv.id, [r.is_default for r in rows]

    cv_id, defaults = asyncio.run(_run())
    assert cv_id
    # first CV of its kind auto-becomes default
    assert defaults == [True]


def test_update_sections_roundtrip(temp_db):
    from app.db.connection import session_scope
    from app.db.services.cvs import create_cv, cv_to_dict, get_cv, update_cv
    from app.models.cv_schemas import CVSections

    async def _run():
        async with session_scope() as session:
            cv = await create_cv(session, title="Base")
            new_sections = CVSections(
                summary="Hello",
                skills=["Python", "FastAPI"],
            )
            await update_cv(session, cv.id, sections=new_sections)
        async with session_scope() as session:
            cv = await get_cv(session, cv.id)
            return cv_to_dict(cv)

    data = asyncio.run(_run())
    assert data["sections"]["summary"] == "Hello"
    assert data["sections"]["skills"] == ["Python", "FastAPI"]


def test_is_default_unique_per_kind(temp_db):
    from app.db.connection import session_scope
    from app.db.services.cvs import create_cv, list_cvs

    async def _run():
        async with session_scope() as session:
            await create_cv(session, title="CV A", kind="cv")
            await create_cv(session, title="CV B", kind="cv", is_default=True)
            await create_cv(session, title="Port A", kind="portfolio")
            rows = await list_cvs(session)
        return [(r.kind, r.title, r.is_default) for r in rows]

    rows = asyncio.run(_run())
    cv_rows = [r for r in rows if r[0] == "cv"]
    assert sum(1 for r in cv_rows if r[2]) == 1
    # portfolio's first entry auto-default
    port_rows = [r for r in rows if r[0] == "portfolio"]
    assert port_rows[0][2] is True


def test_delete_promotes_new_default(temp_db):
    from app.db.connection import session_scope
    from app.db.services.cvs import create_cv, delete_cv, list_cvs

    async def _run():
        async with session_scope() as session:
            a = await create_cv(session, title="A")
            await create_cv(session, title="B")
            await delete_cv(session, a.id)
            rows = await list_cvs(session)
        return [(r.title, r.is_default) for r in rows]

    rows = asyncio.run(_run())
    assert len(rows) == 1
    assert rows[0] == ("B", True)


def test_clone_cv_preserves_sections(temp_db):
    from app.db.connection import session_scope
    from app.db.services.cvs import clone_cv, create_cv, cv_to_dict
    from app.models.cv_schemas import CVSections

    async def _run():
        async with session_scope() as session:
            src = await create_cv(
                session,
                title="Base",
                sections=CVSections(skills=["Go", "Rust"]),
            )
            cloned = await clone_cv(session, src.id, new_title="Base — Acme")
        return cv_to_dict(cloned)

    data = asyncio.run(_run())
    assert data["title"] == "Base — Acme"
    assert data["sections"]["skills"] == ["Go", "Rust"]
    assert data["tailored_from_cv_id"]


# ---------------------------------------------------------------------------
# Renderer (HTML only — PDF needs Chromium, skipped in CI)
# ---------------------------------------------------------------------------


def test_render_html_all_templates():
    from app.models.cv_schemas import (
        Contact,
        CVSections,
        ExperienceEntry,
        ProjectEntry,
    )
    from app.services.cv_renderer import TEMPLATE_FILES, render_html

    sections = CVSections(
        contact=Contact(full_name="Thanh Nhan", email="a@b.com", github="https://github.com/x"),
        summary="Senior Python engineer.",
        skills=["Python", "FastAPI"],
        experience=[
            ExperienceEntry(
                company="Acme",
                title="Lead",
                start="2022",
                end="Present",
                bullets=["Built scalable services"],
            )
        ],
        projects=[ProjectEntry(name="JARVIS", url="https://example.com", tech=["Python"])],
    )
    for template in TEMPLATE_FILES.keys():
        html = render_html(sections, template=template, title="Thanh Nhan CV")
        assert "<html" in html.lower()
        assert "Thanh Nhan" in html
        assert "Python" in html


# ---------------------------------------------------------------------------
# Tailor — mock the LLM so we don't hit the network.
# ---------------------------------------------------------------------------


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def ainvoke(self, _prompt: str) -> _FakeMessage:
        return _FakeMessage(json.dumps(self._payload))


def test_tailor_cv_rewrites_summary(monkeypatch):
    from app.models.cv_schemas import CVSections
    from app.services import cv_tailor as tailor_mod

    tailored_payload = {
        "sections": {
            "contact": {"full_name": "", "email": "", "phone": "", "location": "", "website": "", "linkedin": "", "github": ""},
            "summary": "Rewritten for Acme — Python/FastAPI specialist.",
            "experience": [],
            "education": [],
            "skills": ["Python", "FastAPI"],
            "projects": [],
            "certifications": [],
            "languages": [],
            "custom": [],
        },
        "rationale": "Reworded summary, prioritised Python/FastAPI skills.",
    }
    fake_llm = _FakeLLM(tailored_payload)

    with patch(
        "app.agent.brain.build_llm_with_fallback",
        return_value=(fake_llm, "fake", "fake-model"),
    ):
        sections = CVSections(summary="Old summary.", skills=["Python"])
        job = {
            "title": "Senior Python Engineer",
            "company": "Acme",
            "location": "Remote",
            "description": "Python + FastAPI role.",
        }
        new_sections, rationale = asyncio.run(tailor_mod.tailor_cv(sections, job))

    assert new_sections.summary.startswith("Rewritten for Acme")
    assert "Python" in new_sections.skills
    assert "summary" in rationale.lower() or "Rework" in rationale


def test_tailor_cv_fallback_on_invalid_llm_output(monkeypatch):
    from app.models.cv_schemas import CVSections
    from app.services import cv_tailor as tailor_mod

    fake_llm = _FakeLLM({"nonsense": True})
    with patch(
        "app.agent.brain.build_llm_with_fallback",
        return_value=(fake_llm, "fake", "fake-model"),
    ):
        sections = CVSections(summary="Untouched.")
        new_sections, rationale = asyncio.run(
            tailor_mod.tailor_cv(sections, {"title": "x", "company": "y"})
        )

    assert new_sections.summary == "Untouched."
    assert "fail" in rationale.lower() or "schema" in rationale.lower()


# ---------------------------------------------------------------------------
# cv_manager tool
# ---------------------------------------------------------------------------


def test_cv_manager_list_empty(temp_db):
    from app.tools.cv_manager import CVManagerTool

    result = asyncio.run(CVManagerTool().execute(action="list"))
    assert result.success is True
    assert result.data["count"] == 0


def test_cv_manager_get_uses_default(temp_db):
    from app.db.connection import session_scope
    from app.db.services.cvs import create_cv
    from app.tools.cv_manager import CVManagerTool

    async def _seed():
        async with session_scope() as session:
            await create_cv(session, title="Default CV")

    asyncio.run(_seed())
    result = asyncio.run(CVManagerTool().execute(action="get"))
    assert result.success is True
    assert result.data["title"] == "Default CV"


def test_cv_manager_unknown_action(temp_db):
    from app.tools.cv_manager import CVManagerTool

    result = asyncio.run(CVManagerTool().execute(action="does_not_exist"))
    assert result.success is False
    assert "Unknown" in (result.error or "")


def test_cv_manager_tailor_requires_job_id(temp_db):
    from app.tools.cv_manager import CVManagerTool

    result = asyncio.run(CVManagerTool().execute(action="tailor_for_job"))
    assert result.success is False
    assert "job_id" in (result.error or "").lower()
