"""Job ↔ profile matching — cheap Jaccard-style scorer."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/-]{1,}")


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORD_RE.finditer(text or "")}


def score_job(job: dict, profile: dict | None) -> float:
    """Return a 0..1 match score for ``job`` against ``profile``.

    The score is the Jaccard overlap between the profile's skills + titles
    set and the tokens in the job title/description/company. A small
    location bonus is applied when the job's location matches any of the
    user's preferred locations or when remote preference aligns.
    """
    if not profile:
        return 0.0

    skills = {s.lower() for s in (profile.get("skills") or [])}
    titles = {t.lower() for t in (profile.get("preferred_titles") or [])}
    profile_tokens = skills | _tokens(" ".join(profile.get("preferred_titles") or []))
    if not profile_tokens:
        return 0.0

    job_hay = " ".join(
        [
            str(job.get("title") or ""),
            str(job.get("company") or ""),
            str(job.get("description") or ""),
        ]
    )
    job_tokens = _tokens(job_hay)
    if not job_tokens:
        return 0.0

    overlap = profile_tokens & job_tokens
    if not overlap:
        score = 0.0
    else:
        union = profile_tokens | job_tokens
        score = len(overlap) / len(union)

    # Title keyword boost — title match is the strongest signal.
    title_tokens = _tokens(str(job.get("title") or ""))
    if titles & {t for t in titles if any(t in tt for tt in title_tokens)}:
        score = min(1.0, score + 0.1)

    # Location bonus
    loc_prefs = [s.lower() for s in (profile.get("preferred_locations") or [])]
    job_loc = str(job.get("location") or "").lower()
    if loc_prefs and any(loc in job_loc for loc in loc_prefs if loc):
        score = min(1.0, score + 0.05)

    # Remote alignment
    if profile.get("preferred_remote") and job.get("remote"):
        score = min(1.0, score + 0.05)

    return round(score, 4)
