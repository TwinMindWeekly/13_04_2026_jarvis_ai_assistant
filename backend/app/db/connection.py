"""Async SQLAlchemy engine / session / bootstrap helpers.

SQLite is configured with `PRAGMA foreign_keys=ON` and `journal_mode=WAL`
on every new connection. Tables are created via ``Base.metadata.create_all``
(no Alembic yet — the plan marks migrations as optional for dev).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)


def _resolve_sqlite_path() -> Path:
    """Resolve the SQLite file path relative to the backend directory."""
    raw = getattr(settings, "sqlite_path", "./jarvis.db")
    p = Path(raw)
    if not p.is_absolute():
        # Backend root = three parents up from this file (app/db/connection.py).
        backend_root = Path(__file__).resolve().parent.parent.parent
        p = backend_root / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _build_engine() -> AsyncEngine:
    path = _resolve_sqlite_path()
    url = f"sqlite+aiosqlite:///{path.as_posix()}"
    engine = create_async_engine(
        url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record) -> None:  # noqa: ANN001
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
        finally:
            cur.close()

    return engine


engine: AsyncEngine = _build_engine()
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


_FTS5_DDL = [
    # email_messages_fts — indexes subject + from + body.
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS email_messages_fts USING fts5(
        subject, from_addr, body,
        content='email_messages', content_rowid='id',
        tokenize='unicode61 remove_diacritics 2'
    )
    """,
    # Triggers to keep FTS5 in sync.
    """
    CREATE TRIGGER IF NOT EXISTS email_messages_ai AFTER INSERT ON email_messages BEGIN
        INSERT INTO email_messages_fts(rowid, subject, from_addr, body)
        VALUES (new.id, new.subject, new.from_addr, new.body);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS email_messages_ad AFTER DELETE ON email_messages BEGIN
        INSERT INTO email_messages_fts(email_messages_fts, rowid, subject, from_addr, body)
        VALUES ('delete', old.id, old.subject, old.from_addr, old.body);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS email_messages_au AFTER UPDATE ON email_messages BEGIN
        INSERT INTO email_messages_fts(email_messages_fts, rowid, subject, from_addr, body)
        VALUES ('delete', old.id, old.subject, old.from_addr, old.body);
        INSERT INTO email_messages_fts(rowid, subject, from_addr, body)
        VALUES (new.id, new.subject, new.from_addr, new.body);
    END
    """,
]


def _fts5_supported() -> bool:
    """Return True if the embedded SQLite build has FTS5 compiled in.

    When False, ``init_db`` falls back to LIKE queries in Phase 2.
    """
    import sqlite3  # noqa: PLC0415

    try:
        conn = sqlite3.connect(":memory:")
        opts = [r[0] for r in conn.execute("PRAGMA compile_options")]
        conn.close()
        return "ENABLE_FTS5" in opts
    except Exception:
        return False


async def init_db() -> None:
    """Create all tables + FTS5 virtual table (if supported)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if _fts5_supported():
            for ddl in _FTS5_DDL:
                await conn.exec_driver_sql(ddl)
    logger.info(
        "SQLite DB ready — %s (FTS5=%s)",
        _resolve_sqlite_path(),
        "on" if _fts5_supported() else "off",
    )


async def reset_engine_for_path(path: str) -> None:
    """Swap the engine to a new SQLite file (used by tests).

    Tests monkey-patch ``settings.sqlite_path`` then call this helper so the
    process continues with a fresh DB file. Not intended for production.
    """
    global engine, AsyncSessionLocal
    await engine.dispose()
    from app.core.config import settings as _s

    _s.sqlite_path = path
    engine = _build_engine()
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an ``AsyncSession``."""
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context manager version for non-FastAPI callers (background tasks, tools)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
