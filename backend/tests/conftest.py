"""Shared pytest fixtures for JARVIS AI Assistant backend tests."""

import asyncio

import pytest
from unittest.mock import patch, MagicMock

from app.models.schemas import ChatMessage, MessageRole


@pytest.fixture
def mock_settings():
    """Patch app.core.config.settings with test values (no real API keys)."""
    fake_settings = MagicMock()
    fake_settings.openai_api_key = "test-key-openai"
    fake_settings.google_api_key = "test-key-gemini"
    fake_settings.anthropic_api_key = "test-key-claude"
    fake_settings.ollama_base_url = "http://localhost:11434"
    fake_settings.default_provider = "openai"
    fake_settings.default_model = "gpt-4o"
    fake_settings.host = "0.0.0.0"
    fake_settings.port = 8000
    fake_settings.debug = False
    fake_settings.cors_origins = ["http://localhost:5173"]

    with patch("app.core.config.settings", fake_settings), \
         patch("app.routers.chat.settings", fake_settings):
        yield fake_settings


@pytest.fixture
def test_messages() -> list[ChatMessage]:
    """Return a minimal message list with a system message and a user message."""
    return [
        ChatMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        ChatMessage(role=MessageRole.USER, content="Hello, world!"),
    ]


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Create a fresh SQLite DB for a single test and dispose of it afterwards.

    Usage::

        def test_something(temp_db):
            # temp_db == Path to the sqlite file; the global engine is also swapped.
    """
    from app.core.config import settings
    from app.db import connection as conn_mod

    db_path = tmp_path / "jarvis-test.db"
    monkeypatch.setattr(settings, "sqlite_path", str(db_path))

    async def _setup() -> None:
        await conn_mod.reset_engine_for_path(str(db_path))
        await conn_mod.init_db()

    asyncio.run(_setup())

    yield db_path

    async def _teardown() -> None:
        await conn_mod.engine.dispose()

    try:
        asyncio.run(_teardown())
    except Exception:
        pass
