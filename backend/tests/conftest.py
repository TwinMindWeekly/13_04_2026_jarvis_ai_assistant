"""Shared pytest fixtures for JARVIS AI Assistant backend tests."""

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
