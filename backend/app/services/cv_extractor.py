"""CV text → structured profile fields (skills, titles, locations) via LLM.

Uses the same LangChain provider chain as the agent brain, but with a
plain-string prompt and a small JSON output. Failures are non-fatal —
callers fall back to the CV text stored verbatim so the user can edit.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


_PROMPT_TEMPLATE = """Extract structured career information from the CV text below.

Return ONLY a JSON object with exactly these fields (no markdown fences):
- full_name: string (best-effort name; "" if unclear)
- headline: string (one-line professional summary, e.g. "Senior Python Engineer — 6 yrs backend")
- skills: array of strings — technical skills, tools, frameworks, languages (max 30)
- preferred_titles: array of strings — up to 5 job titles the person is qualified for
- preferred_locations: array of strings — cities/regions mentioned in the CV (may be empty)
- preferred_remote: boolean — true if the CV mentions remote, WFH, hybrid, or distributed work

CV TEXT:
```
{cv}
```

Respond with the JSON object only."""


async def extract_profile_fields(cv_text: str) -> dict:
    """Return a dict with at least ``skills`` and ``preferred_titles`` keys.

    Keys are guaranteed to exist with sensible defaults so callers don't
    have to guard each lookup. Truncates the CV to 8k chars to stay within
    free-tier context limits.
    """
    fallback = {
        "full_name": "",
        "headline": "",
        "skills": [],
        "preferred_titles": [],
        "preferred_locations": [],
        "preferred_remote": False,
    }
    text = (cv_text or "").strip()
    if len(text) < 40:
        return fallback

    truncated = text[:8000]
    prompt = _PROMPT_TEMPLATE.format(cv=truncated)

    try:
        from app.agent.brain import build_llm_with_fallback  # noqa: PLC0415

        llm, _, _ = build_llm_with_fallback(provider="auto", model="")
        response = await llm.ainvoke(prompt)
        raw = getattr(response, "content", response)
        if isinstance(raw, list):
            raw = "".join(
                part.get("text", "") for part in raw if isinstance(part, dict) and part.get("type") == "text"
            )
        if not isinstance(raw, str):
            raw = str(raw)
        # Strip markdown code fences if the model added them.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return fallback
        parsed = json.loads(match.group(0))
    except Exception as exc:
        logger.warning("CV extraction failed (non-fatal): %s", exc)
        return fallback

    def _strlist(key: str, limit: int) -> list[str]:
        v = parsed.get(key, [])
        if not isinstance(v, list):
            return []
        return [str(x).strip() for x in v if str(x).strip()][:limit]

    return {
        "full_name": str(parsed.get("full_name", "")).strip(),
        "headline": str(parsed.get("headline", "")).strip(),
        "skills": _strlist("skills", 30),
        "preferred_titles": _strlist("preferred_titles", 5),
        "preferred_locations": _strlist("preferred_locations", 10),
        "preferred_remote": bool(parsed.get("preferred_remote", False)),
    }


# ---------------------------------------------------------------------------
# Phase 19 — full-CV extractor for the cvs table
# ---------------------------------------------------------------------------


_FULL_PROMPT = """You are a CV parser. Extract a structured resume from the text below.

Return ONLY a JSON object (no markdown fences, no commentary) matching this schema:
{{
  "contact": {{"full_name": str, "email": str, "phone": str, "location": str, "website": str, "linkedin": str, "github": str}},
  "summary": str,
  "experience": [{{"company": str, "title": str, "start": str, "end": str, "location": str, "bullets": [str]}}],
  "education": [{{"school": str, "degree": str, "field": str, "start": str, "end": str, "gpa": str}}],
  "skills": [str],
  "projects": [{{"name": str, "url": str, "description": str, "tech": [str]}}],
  "certifications": [{{"name": str, "issuer": str, "date": str}}],
  "languages": [{{"name": str, "level": str}}]
}}

Rules:
- Use empty strings / empty arrays when a field is not present.
- Keep dates as they appear (e.g. "Jan 2022", "2022-01", "Present").
- Bullets should be concise sentences, one achievement each. Do NOT invent facts.
- Limit skills to 30, experience and projects to 10 each.

CV TEXT:
```
{cv}
```"""


def _empty_sections() -> dict:
    from app.models.cv_schemas import CVSections  # noqa: PLC0415
    return CVSections().model_dump()


async def parse_to_sections(cv_text: str) -> dict:
    """Return a ``CVSections``-shaped dict parsed from raw CV text.

    Never raises: on LLM failure or invalid JSON, returns an empty
    ``CVSections`` dict so the caller can still create an editable row.
    """
    text = (cv_text or "").strip()
    if len(text) < 40:
        return _empty_sections()

    prompt = _FULL_PROMPT.format(cv=text[:12000])
    raw_json: str | None = None
    try:
        from app.agent.brain import build_llm_with_fallback  # noqa: PLC0415

        llm, _, _ = build_llm_with_fallback(provider="auto", model="")
        response = await llm.ainvoke(prompt)
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = "".join(
                p.get("text", "")
                for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            )
        if not isinstance(content, str):
            content = str(content)
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            raw_json = match.group(0)
    except Exception as exc:
        logger.warning("parse_to_sections LLM call failed: %s", exc)
        return _empty_sections()

    if not raw_json:
        return _empty_sections()

    try:
        parsed = json.loads(raw_json)
    except Exception as exc:
        logger.warning("parse_to_sections invalid JSON: %s", exc)
        return _empty_sections()

    try:
        from app.models.cv_schemas import CVSections  # noqa: PLC0415
        return CVSections.model_validate(parsed).model_dump()
    except Exception as exc:
        logger.warning("parse_to_sections schema mismatch: %s", exc)
        return _empty_sections()
