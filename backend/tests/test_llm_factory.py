"""Tests for LLMFactory.create() — covers provider routing and error cases."""

import sys
import types
import pytest
from unittest.mock import MagicMock  # patch not needed: lazy-import injection used instead

from app.core.exceptions import ProviderAuthError, ProviderNotFoundError
from app.services.llm_factory import LLMFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inject_fake_provider(module_path: str, class_name: str):
    """
    Inject a fake module into sys.modules so that the lazy
    `from <module_path> import <class_name>` inside LLMFactory.create()
    returns a MagicMock instead of trying to import the real SDK.

    Returns (fake_class, fake_module) so the caller can assert on the class.
    """
    fake_class = MagicMock(name=class_name)
    fake_module = types.ModuleType(module_path)
    setattr(fake_module, class_name, fake_class)
    sys.modules[module_path] = fake_module
    return fake_class


def _remove_fake_module(module_path: str) -> None:
    sys.modules.pop(module_path, None)


# ---------------------------------------------------------------------------
# Successful creation
# ---------------------------------------------------------------------------


def test_create_openai_provider():
    """LLMFactory.create('openai', ...) returns an OpenAIProvider instance."""
    mod = "app.services.providers.openai_provider"
    _remove_fake_module(mod)
    fake_cls = _inject_fake_provider(mod, "OpenAIProvider")
    try:
        result = LLMFactory.create(provider="openai", model="gpt-4o", api_key="test-key")
    finally:
        _remove_fake_module(mod)
    fake_cls.assert_called_once_with(api_key="test-key", model="gpt-4o")
    assert result is fake_cls.return_value


def test_create_gemini_provider():
    """LLMFactory.create('gemini', ...) returns a GeminiProvider instance."""
    mod = "app.services.providers.gemini_provider"
    _remove_fake_module(mod)
    fake_cls = _inject_fake_provider(mod, "GeminiProvider")
    try:
        result = LLMFactory.create(provider="gemini", model="gemini-2.0-flash", api_key="test-key")
    finally:
        _remove_fake_module(mod)
    fake_cls.assert_called_once_with(api_key="test-key", model="gemini-2.0-flash")
    assert result is fake_cls.return_value


def test_create_claude_provider():
    """LLMFactory.create('claude', ...) returns a ClaudeProvider instance."""
    mod = "app.services.providers.claude_provider"
    _remove_fake_module(mod)
    fake_cls = _inject_fake_provider(mod, "ClaudeProvider")
    try:
        result = LLMFactory.create(provider="claude", model="claude-sonnet-4-20250514", api_key="test-key")
    finally:
        _remove_fake_module(mod)
    fake_cls.assert_called_once_with(api_key="test-key", model="claude-sonnet-4-20250514")
    assert result is fake_cls.return_value


def test_create_ollama_provider():
    """LLMFactory.create('ollama', ...) returns an OllamaProvider — no api_key needed."""
    mod = "app.services.providers.ollama_provider"
    _remove_fake_module(mod)
    fake_cls = _inject_fake_provider(mod, "OllamaProvider")
    try:
        result = LLMFactory.create(
            provider="ollama",
            model="llama3.2",
            base_url="http://localhost:11434",
        )
    finally:
        _remove_fake_module(mod)
    fake_cls.assert_called_once_with(base_url="http://localhost:11434", model="llama3.2")
    assert result is fake_cls.return_value


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_create_unknown_provider_raises():
    """LLMFactory.create() raises ProviderNotFoundError for an unknown provider name."""
    with pytest.raises(ProviderNotFoundError):
        LLMFactory.create(provider="unknown", model="x", api_key="key")


def test_create_cloud_provider_without_key_raises():
    """LLMFactory.create('openai', ...) raises ProviderAuthError when api_key is empty."""
    with pytest.raises(ProviderAuthError):
        LLMFactory.create(provider="openai", model="gpt-4o", api_key="")


def test_create_gemini_without_key_raises():
    """LLMFactory.create('gemini', ...) raises ProviderAuthError when api_key is empty."""
    with pytest.raises(ProviderAuthError):
        LLMFactory.create(provider="gemini", model="gemini-2.0-flash", api_key="")


def test_create_claude_without_key_raises():
    """LLMFactory.create('claude', ...) raises ProviderAuthError when api_key is empty."""
    with pytest.raises(ProviderAuthError):
        LLMFactory.create(provider="claude", model="claude-sonnet-4-20250514", api_key="")


# ---------------------------------------------------------------------------
# Input normalisation
# ---------------------------------------------------------------------------


def test_create_provider_case_insensitive():
    """Provider name matching is case-insensitive: 'OpenAI' and 'OPENAI' both work."""
    mod = "app.services.providers.openai_provider"

    _remove_fake_module(mod)
    fake_cls = _inject_fake_provider(mod, "OpenAIProvider")
    try:
        LLMFactory.create(provider="OpenAI", model="gpt-4o", api_key="test-key")
    finally:
        _remove_fake_module(mod)
    fake_cls.assert_called_once()

    _remove_fake_module(mod)
    fake_cls2 = _inject_fake_provider(mod, "OpenAIProvider")
    try:
        LLMFactory.create(provider="OPENAI", model="gpt-4o", api_key="test-key")
    finally:
        _remove_fake_module(mod)
    fake_cls2.assert_called_once()


def test_create_provider_strips_whitespace():
    """Leading/trailing whitespace in provider name is stripped before matching."""
    mod = "app.services.providers.openai_provider"
    _remove_fake_module(mod)
    fake_cls = _inject_fake_provider(mod, "OpenAIProvider")
    try:
        result = LLMFactory.create(provider=" openai ", model="gpt-4o", api_key="test-key")
    finally:
        _remove_fake_module(mod)
    fake_cls.assert_called_once_with(api_key="test-key", model="gpt-4o")
    assert result is fake_cls.return_value
