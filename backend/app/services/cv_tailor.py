"""LLM rewrite of CV sections for a specific job posting (Phase 19)."""

from __future__ import annotations

import json
import logging
import re

from app.models.cv_schemas import CVSections

logger = logging.getLogger(__name__)


_TAILOR_PROMPT = """You are an expert résumé writer. Rewrite the CV below so it targets the job posting.

Rules — follow strictly:
1. DO NOT invent employers, titles, schools, degrees, dates, or certifications that aren't already in the CV.
2. Rewrite the "summary" so it highlights the job's must-have skills the candidate genuinely has.
3. Reorder and emphasize "skills" so the job's required technologies appear first. Keep real skills from the CV only.
4. For every experience entry, rewrite each bullet to be concise (start with an action verb, 1 sentence, quantify impact when possible, echo relevant keywords from the JD naturally). Keep the same company/title/dates.
5. Keep "education", "certifications", "languages", "projects" unchanged.
6. Output must be valid JSON matching the schema below — no markdown fences, no commentary.

Schema (exact keys):
{{
  "sections": {{ /* same CVSections schema you received */ }},
  "rationale": str  /* 1-2 sentences explaining the main changes you made */
}}

# JOB POSTING
Title: {job_title}
Company: {job_company}
Location: {job_location}
Description:
{job_description}

# ORIGINAL CV (CVSections JSON)
{sections_json}
"""


async def tailor_cv(sections: CVSections, job: dict) -> tuple[CVSections, str]:
    """Return ``(new_sections, rationale)`` tailored for ``job``.

    Non-fatal on any LLM/JSON error — falls back to the original sections
    with a rationale explaining the failure so the caller can still clone.
    """
    payload = {
        "job_title": str(job.get("title", "")).strip(),
        "job_company": str(job.get("company", "")).strip(),
        "job_location": str(job.get("location", "")).strip(),
        "job_description": (str(job.get("description", "")).strip() or "(no description)")[:4000],
        "sections_json": json.dumps(sections.model_dump(), ensure_ascii=False),
    }
    prompt = _TAILOR_PROMPT.format(**payload)

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
        if not match:
            return sections, "Tailor failed: LLM returned no JSON object."
        parsed = json.loads(match.group(0))
    except Exception as exc:
        logger.warning("tailor_cv LLM call failed: %s", exc)
        return sections, f"Tailor failed: {exc}"

    if not isinstance(parsed.get("sections"), dict):
        return sections, "Tailor failed: LLM did not return a 'sections' object."
    try:
        new_sections = CVSections.model_validate(parsed["sections"])
    except Exception as exc:
        logger.warning("tailor_cv schema mismatch: %s", exc)
        return sections, f"Tailor failed: schema mismatch — {exc}"

    rationale = str(parsed.get("rationale") or "").strip() or "CV tailored for this role."
    return new_sections, rationale
