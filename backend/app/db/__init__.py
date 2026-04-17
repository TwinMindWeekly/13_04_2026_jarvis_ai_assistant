"""SQLite + SQLAlchemy 2 async persistence layer for JARVIS.

Exposes:
  - engine / AsyncSessionLocal / get_session (connection)
  - Base and ORM models (models)
  - init_db / migrate_json_if_needed (bootstrap helpers)

This replaces the earlier `uploads/documents_metadata.json` file with a real
database so agent tools can query metadata and wikilinks instead of pushing
the entire JSON payload through the prompt.
"""

from app.db.connection import (
    AsyncSessionLocal,
    engine,
    get_session,
    init_db,
    session_scope,
)
from app.db.models import (
    Base,
    Document,
    EmailAccount,
    EmailMessage,
    Job,
    SavedJobSearch,
    UserProfile,
    Wikilink,
)

__all__ = [
    "AsyncSessionLocal",
    "Base",
    "Document",
    "EmailAccount",
    "EmailMessage",
    "Job",
    "SavedJobSearch",
    "UserProfile",
    "Wikilink",
    "engine",
    "get_session",
    "init_db",
    "session_scope",
]
