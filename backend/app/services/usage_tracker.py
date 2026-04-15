"""Singleton usage tracker — counts requests/tokens per LLM provider.

Persists to a JSON file so stats survive backend restarts.
Daily counters reset at midnight UTC automatically.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock

from app.core.config import settings

logger = logging.getLogger(__name__)

_USAGE_FILENAME = "usage.json"

# Known daily limits per provider (free tier).
_PROVIDER_LIMITS: dict[str, dict] = {
    "groq": {
        "daily_request_limit": 1000,
        "rpm_limit": 30,
        "tpm_limit": 12000,
    },
    "gemini": {
        "daily_request_limit": 20,
        "rpm_limit": 10,
        "tpm_limit": 0,
    },
    "sambanova": {
        "daily_request_limit": 200,
        "rpm_limit": 20,
        "tpm_limit": 0,
    },
    "openai": {
        "daily_request_limit": 0,  # pay-per-use, no daily cap
        "rpm_limit": 60,
        "tpm_limit": 0,
    },
    "claude": {
        "daily_request_limit": 0,
        "rpm_limit": 60,
        "tpm_limit": 0,
    },
    "ollama": {
        "daily_request_limit": 0,  # local, unlimited
        "rpm_limit": 0,
        "tpm_limit": 0,
    },
}


def _empty_provider_stats(provider: str, model: str = "") -> dict:
    """Return a fresh stats dict for a provider."""
    limits = _PROVIDER_LIMITS.get(provider, {})
    return {
        "provider": provider,
        "model": model,
        "requests_today": 0,
        "tokens_in_today": 0,
        "tokens_out_today": 0,
        "daily_request_limit": limits.get("daily_request_limit", 0),
        "rpm_limit": limits.get("rpm_limit", 0),
        "tpm_limit": limits.get("tpm_limit", 0),
        "last_used_at": "",
        "resets_at": _next_midnight_utc().isoformat(),
        "last_error": None,
    }


def _next_midnight_utc() -> datetime:
    """Return the next midnight UTC."""
    now = datetime.now(timezone.utc)
    tomorrow = now.date() + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc)


def _today_utc_str() -> str:
    """Return today's date as YYYY-MM-DD in UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class UsageTracker:
    """Thread-safe singleton that tracks LLM usage per provider."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._data: dict = {"date": _today_utc_str(), "providers": {}}
        self._path = Path(settings.upload_dir) / _USAGE_FILENAME
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        provider: str,
        model: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
        error: str | None = None,
    ) -> None:
        """Record one request for the given provider."""
        with self._lock:
            self._check_daily_reset()
            stats = self._ensure_provider(provider, model)
            stats["requests_today"] += 1
            stats["tokens_in_today"] += tokens_in
            stats["tokens_out_today"] += tokens_out
            stats["last_used_at"] = datetime.now(timezone.utc).isoformat()
            if model:
                stats["model"] = model
            if error:
                stats["last_error"] = error
            else:
                stats["last_error"] = None
            self._persist()

    def record_error(self, provider: str, model: str, error: str) -> None:
        """Record a failed request (quota error, auth error, etc)."""
        with self._lock:
            self._check_daily_reset()
            stats = self._ensure_provider(provider, model)
            stats["last_error"] = error
            stats["last_used_at"] = datetime.now(timezone.utc).isoformat()
            self._persist()

    def get_all(self) -> dict:
        """Return usage stats for all providers."""
        with self._lock:
            self._check_daily_reset()
            return {
                "date": self._data["date"],
                "resets_at": _next_midnight_utc().isoformat(),
                "providers": dict(self._data["providers"]),
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_provider(self, provider: str, model: str = "") -> dict:
        """Get or create stats entry for a provider."""
        key = provider.lower()
        if key not in self._data["providers"]:
            self._data["providers"][key] = _empty_provider_stats(key, model)
        return self._data["providers"][key]

    def _check_daily_reset(self) -> None:
        """Reset daily counters if date has changed (midnight UTC)."""
        today = _today_utc_str()
        if self._data["date"] != today:
            logger.info("Daily usage reset — %s → %s", self._data["date"], today)
            for stats in self._data["providers"].values():
                stats["requests_today"] = 0
                stats["tokens_in_today"] = 0
                stats["tokens_out_today"] = 0
                stats["last_error"] = None
                stats["resets_at"] = _next_midnight_utc().isoformat()
            self._data["date"] = today
            self._persist()

    def _persist(self) -> None:
        """Write current stats to JSON file."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Failed to persist usage data: %s", exc)

    def _load(self) -> None:
        """Load stats from JSON file if it exists."""
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "providers" in raw:
                self._data = raw
                self._check_daily_reset()
                logger.info("Loaded usage data: %d providers", len(self._data["providers"]))
        except Exception as exc:
            logger.warning("Failed to load usage data: %s", exc)


# Module-level singleton.
usage_tracker = UsageTracker()
