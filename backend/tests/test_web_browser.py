"""Tests for WebBrowserTool in web_browser.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.web_browser import WebBrowserTool
from app.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_page(body_text: str = "Page content here") -> MagicMock:
    """Build a minimal fake Playwright page object."""
    page = MagicMock()
    page.goto = AsyncMock(return_value=None)
    page.inner_text = AsyncMock(return_value=body_text)
    page.close = AsyncMock(return_value=None)
    return page


def _make_fake_browser(page: MagicMock) -> MagicMock:
    """Build a minimal fake Playwright browser that returns *page* on new_page()."""
    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=page)
    return browser


def _make_fake_llm(content) -> MagicMock:
    """Build a fake LangChain LLM whose .invoke() returns an object with .content."""
    response = MagicMock()
    response.content = content
    llm = MagicMock()
    llm.invoke = MagicMock(return_value=response)
    return llm


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestWebBrowserSchema:
    """Verify that the tool schema contains the required fields."""

    def test_action_enum_includes_summarize(self) -> None:
        tool = WebBrowserTool()
        action_enum = tool.parameters["properties"]["action"]["enum"]
        assert "summarize" in action_enum

    def test_instructions_param_exists(self) -> None:
        tool = WebBrowserTool()
        assert "instructions" in tool.parameters["properties"]

    def test_max_chars_param_exists(self) -> None:
        tool = WebBrowserTool()
        assert "max_chars" in tool.parameters["properties"]


# ---------------------------------------------------------------------------
# summarize — missing instructions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_missing_instructions_returns_failure() -> None:
    """summarize with empty instructions returns ToolResult(success=False)."""
    tool = WebBrowserTool()
    # We call _handle_summarize directly to avoid browser setup.
    fake_page = _make_fake_page("irrelevant")
    result = await tool._handle_summarize(fake_page, "https://example.com", "", 0)

    assert result.success is False
    assert result.error is not None
    assert "instructions" in result.error.lower() or "required" in result.error.lower()


@pytest.mark.asyncio
async def test_summarize_whitespace_only_instructions_returns_failure() -> None:
    """summarize with whitespace-only instructions also fails."""
    tool = WebBrowserTool()
    fake_page = _make_fake_page("irrelevant")
    result = await tool._handle_summarize(fake_page, "https://example.com", "   ", 0)
    assert result.success is False


# ---------------------------------------------------------------------------
# summarize — success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_success_path(monkeypatch) -> None:
    """summarize with valid instructions returns LLM summary in result.data."""
    tool = WebBrowserTool()
    fake_page = _make_fake_page("Some page content")
    fake_llm = _make_fake_llm("## Summary\n- point")

    fake_settings = MagicMock()
    fake_settings.default_provider = "gemini"
    fake_settings.default_model = "gemini-3-flash"

    with patch("app.agent.brain.build_llm_with_fallback", return_value=(fake_llm, "gemini", "gemini-3-flash")), \
         patch("app.tools.web_browser.WebBrowserTool._ensure_browser", new_callable=AsyncMock), \
         patch("app.core.config.settings", fake_settings):
        result = await tool._handle_summarize(
            fake_page, "https://example.com", "Summarize the page", 0
        )

    assert result.success is True
    assert result.data == "## Summary\n- point"
    assert result.metadata["model_used"] == "gemini/gemini-3-flash"
    assert result.metadata["action"] == "summarize"
    assert result.metadata["instructions"] == "Summarize the page"


@pytest.mark.asyncio
async def test_summarize_success_via_execute(monkeypatch) -> None:
    """summarize through execute() with browser mocked at class level."""
    tool = WebBrowserTool()
    body_text = "Hello from the page"
    fake_page = _make_fake_page(body_text)
    fake_browser = _make_fake_browser(fake_page)
    fake_llm = _make_fake_llm("LLM summary result")

    fake_settings = MagicMock()
    fake_settings.default_provider = "gemini"
    fake_settings.default_model = "gemini-3-flash"

    monkeypatch.setattr(WebBrowserTool, "_browser", fake_browser)

    async def _noop_ensure(self) -> None:
        pass

    monkeypatch.setattr(WebBrowserTool, "_ensure_browser", _noop_ensure)

    with patch("app.agent.brain.build_llm_with_fallback", return_value=(fake_llm, "gemini", "gemini-3-flash")), \
         patch("app.core.config.settings", fake_settings):
        result = await tool.execute(
            url="https://example.com",
            action="summarize",
            instructions="Extract the main content",
        )

    assert result.success is True
    assert result.data == "LLM summary result"
    assert result.metadata["action"] == "summarize"


# ---------------------------------------------------------------------------
# summarize — LLM failure fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_llm_raises_returns_raw_text() -> None:
    """When LLM raises, result.success=True with raw text and summarization_failed=True."""
    tool = WebBrowserTool()
    fake_page = _make_fake_page("Raw page text")
    fake_llm = MagicMock()
    fake_llm.invoke = MagicMock(side_effect=RuntimeError("LLM down"))

    fake_settings = MagicMock()
    fake_settings.default_provider = "openai"
    fake_settings.default_model = "gpt-4o"

    with patch("app.agent.brain.build_llm_with_fallback", return_value=(fake_llm, "openai", "gpt-4o")), \
         patch("app.core.config.settings", fake_settings):
        result = await tool._handle_summarize(
            fake_page, "https://example.com", "Extract info", 0
        )

    assert result.success is True
    assert "Raw page text" in result.data
    assert result.metadata.get("summarization_failed") is True


# ---------------------------------------------------------------------------
# summarize — Gemini list-of-dicts content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_gemini_list_content() -> None:
    """Gemini list-of-dicts .content is joined into a single string."""
    tool = WebBrowserTool()
    fake_page = _make_fake_page("Page body")
    gemini_content = [
        {"type": "text", "text": "A"},
        {"type": "text", "text": "B"},
    ]
    fake_llm = _make_fake_llm(gemini_content)

    fake_settings = MagicMock()
    fake_settings.default_provider = "gemini"
    fake_settings.default_model = "gemini-2.5-flash"

    with patch("app.agent.brain.build_llm_with_fallback", return_value=(fake_llm, "gemini", "gemini-2.5-flash")), \
         patch("app.core.config.settings", fake_settings):
        result = await tool._handle_summarize(
            fake_page, "https://example.com", "Summarize", 0
        )

    assert result.success is True
    assert result.data == "A\nB"


# ---------------------------------------------------------------------------
# summarize — max_chars truncation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_max_chars_truncation() -> None:
    """When page text exceeds max_chars, '[...truncated]' appears in the raw fallback text."""
    tool = WebBrowserTool()
    long_body = "X" * 200
    fake_page = _make_fake_page(long_body)

    # Force the LLM to raise so the fallback (raw page_text) is returned in data.
    fake_llm = MagicMock()
    fake_llm.invoke = MagicMock(side_effect=RuntimeError("forced LLM failure"))

    fake_settings = MagicMock()
    fake_settings.default_provider = "openai"
    fake_settings.default_model = "gpt-4o"

    with patch("app.agent.brain.build_llm_with_fallback", return_value=(fake_llm, "openai", "gpt-4o")), \
         patch("app.core.config.settings", fake_settings):
        result = await tool._handle_summarize(
            fake_page, "https://example.com", "Summarize", max_chars=50
        )

    assert result.success is True
    assert "[...truncated]" in result.data
    # Should only contain the first 50 chars of body + the marker.
    assert result.data.startswith("X" * 50)
    assert result.metadata["truncated"] is True
