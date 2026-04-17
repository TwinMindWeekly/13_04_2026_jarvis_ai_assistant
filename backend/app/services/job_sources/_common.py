"""Shared helpers for job source adapters."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15.0
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) JARVIS/0.1"
)


def build_client(timeout: float = DEFAULT_TIMEOUT) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": DEFAULT_UA, "Accept-Language": "en-US,en;q=0.9,vi;q=0.8"},
        follow_redirects=True,
    )


def truncate(text: str, limit: int = 500) -> str:
    t = (text or "").strip()
    return t if len(t) <= limit else (t[: limit - 1] + "…")
