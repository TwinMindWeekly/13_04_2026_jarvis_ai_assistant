"""Fernet-based symmetric encryption for credentials stored in SQLite.

The key lives in ``settings.jarvis_secret_key`` (a URL-safe base64 32-byte
Fernet key). When empty on first startup we auto-generate one and persist
it to ``backend/.env`` with a clear log warning — losing the key means all
encrypted email passwords become unrecoverable.

Only one key is active at a time (no rotation yet). Values are encrypted
then base64-encoded so they can round-trip through ``String/Text`` columns.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

_KEY_ENV_VAR = "JARVIS_SECRET_KEY"


def _env_path() -> Path:
    """Return ``backend/.env`` (where pydantic-settings loads from)."""
    backend_root = Path(__file__).resolve().parent.parent.parent
    return backend_root / ".env"


def _persist_key(key: str) -> None:
    """Append ``JARVIS_SECRET_KEY=...`` to ``backend/.env`` (non-destructive)."""
    path = _env_path()
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
    except Exception as exc:
        logger.warning("Could not read %s: %s — secret key lives in memory only", path, exc)
        return
    if _KEY_ENV_VAR in existing:
        return
    suffix = "" if existing.endswith("\n") or not existing else "\n"
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{suffix}{_KEY_ENV_VAR}={key}\n")
        logger.warning(
            "Generated a new %s and wrote it to %s — BACK THIS UP. "
            "Losing this key makes every saved email password unreadable.",
            _KEY_ENV_VAR,
            path,
        )
    except Exception as exc:
        logger.warning(
            "Could not persist %s to %s: %s — re-running will generate a new key",
            _KEY_ENV_VAR,
            path,
            exc,
        )


@lru_cache(maxsize=1)
def get_fernet() -> Fernet:
    """Return a cached Fernet instance keyed by ``settings.jarvis_secret_key``."""
    key = (settings.jarvis_secret_key or "").strip()
    if not key:
        key = Fernet.generate_key().decode("utf-8")
        settings.jarvis_secret_key = key
        _persist_key(key)
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Invalid {_KEY_ENV_VAR}: {exc}. Fernet keys must be 32 url-safe-base64 bytes."
        ) from exc


def encrypt_str(plaintext: str) -> str:
    """Encrypt ``plaintext`` and return a URL-safe base64 token (str)."""
    if plaintext is None:
        return ""
    if plaintext == "":
        return ""
    token = get_fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_str(token: str) -> str:
    """Decrypt a Fernet token back to the original plaintext.

    Returns an empty string when the token is empty or invalid — callers
    should treat that as "no password configured" rather than raising.
    """
    if not token:
        return ""
    try:
        data = get_fernet().decrypt(token.encode("utf-8"))
        return data.decode("utf-8")
    except InvalidToken:
        logger.warning("decrypt_str: invalid token (wrong key?) — returning empty string")
        return ""
    except Exception as exc:
        logger.warning("decrypt_str failed: %s", exc)
        return ""
