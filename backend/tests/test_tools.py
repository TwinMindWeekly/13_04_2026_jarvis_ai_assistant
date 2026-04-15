"""Tests for the JARVIS tool system: BaseTool, ToolResult, ToolRegistry, WebSearchTool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.base import BaseTool, ToolResult
from app.tools.registry import ToolRegistry
from app.tools.web_search import WebSearchTool
from app.tools import create_default_registry


# ---------------------------------------------------------------------------
# Concrete stub used throughout — minimal valid BaseTool subclass
# ---------------------------------------------------------------------------

class _EchoTool(BaseTool):
    name = "echo"
    description = "Echoes back the input string."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to echo"},
        },
        "required": ["text"],
    }

    async def execute(self, text: str = "") -> ToolResult:  # type: ignore[override]
        return ToolResult(success=True, data=text)


class _CounterTool(BaseTool):
    name = "counter"
    description = "Returns a count."
    parameters = {
        "type": "object",
        "properties": {
            "n": {"type": "integer", "description": "Count"},
        },
        "required": ["n"],
    }

    async def execute(self, n: int = 0) -> ToolResult:  # type: ignore[override]
        return ToolResult(success=True, data=n)


# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------


def test_tool_result_success():
    """ToolResult with success=True stores data correctly and has no error."""
    result = ToolResult(success=True, data="hello")
    assert result.success is True
    assert result.data == "hello"
    assert result.error is None


def test_tool_result_failure():
    """ToolResult with success=False stores the error string and has no data."""
    result = ToolResult(success=False, error="bad")
    assert result.success is False
    assert result.error == "bad"
    assert result.data is None


def test_tool_result_metadata_defaults_empty():
    """ToolResult metadata defaults to an empty dict."""
    result = ToolResult(success=True)
    assert result.metadata == {}


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


def test_registry_register_and_get():
    """Registering a tool and retrieving it by name returns the same instance."""
    registry = ToolRegistry()
    tool = _EchoTool()
    registry.register(tool)
    retrieved = registry.get_tool("echo")
    assert retrieved is tool


def test_registry_get_unknown_returns_none():
    """get_tool() returns None for an unregistered name."""
    registry = ToolRegistry()
    assert registry.get_tool("nonexistent") is None


def test_registry_get_all():
    """get_all() returns all registered tools."""
    registry = ToolRegistry()
    echo = _EchoTool()
    counter = _CounterTool()
    registry.register(echo)
    registry.register(counter)
    all_tools = registry.get_all()
    assert len(all_tools) == 2
    names = {t.name for t in all_tools}
    assert names == {"echo", "counter"}


def test_registry_get_all_empty():
    """get_all() returns an empty list when nothing is registered."""
    registry = ToolRegistry()
    assert registry.get_all() == []


def test_registry_get_all_schemas():
    """get_all_schemas() returns dicts with name, description, and parameters keys."""
    registry = ToolRegistry()
    registry.register(_EchoTool())
    registry.register(_CounterTool())
    schemas = registry.get_all_schemas()
    assert len(schemas) == 2
    for schema in schemas:
        assert "name" in schema
        assert "description" in schema
        assert "parameters" in schema
    names = {s["name"] for s in schemas}
    assert names == {"echo", "counter"}


def test_registry_register_overwrites_same_name():
    """Re-registering a tool under the same name replaces the previous one."""
    registry = ToolRegistry()
    tool_v1 = _EchoTool()
    tool_v2 = _EchoTool()
    registry.register(tool_v1)
    registry.register(tool_v2)
    assert registry.get_tool("echo") is tool_v2
    assert len(registry.get_all()) == 1


def test_registry_to_langchain_tools():
    """to_langchain_tools() converts registered tools to StructuredTool instances."""
    from langchain_core.tools import StructuredTool

    registry = ToolRegistry()
    registry.register(_EchoTool())
    lc_tools = registry.to_langchain_tools()
    assert len(lc_tools) == 1
    assert isinstance(lc_tools[0], StructuredTool)
    assert lc_tools[0].name == "echo"


def test_registry_to_langchain_tools_multiple():
    """to_langchain_tools() returns one StructuredTool per registered tool."""
    from langchain_core.tools import StructuredTool

    registry = ToolRegistry()
    registry.register(_EchoTool())
    registry.register(_CounterTool())
    lc_tools = registry.to_langchain_tools()
    assert len(lc_tools) == 2
    names = {t.name for t in lc_tools}
    assert names == {"echo", "counter"}
    assert all(isinstance(t, StructuredTool) for t in lc_tools)


# ---------------------------------------------------------------------------
# WebSearchTool — attributes
# ---------------------------------------------------------------------------


def test_web_search_tool_attributes():
    """WebSearchTool has the required class attributes."""
    tool = WebSearchTool()
    assert tool.name == "web_search"
    assert isinstance(tool.description, str) and len(tool.description) > 0
    assert isinstance(tool.parameters, dict)
    assert "properties" in tool.parameters
    assert "query" in tool.parameters["properties"]


# ---------------------------------------------------------------------------
# WebSearchTool — execute (mocked)
# ---------------------------------------------------------------------------


def _make_ddgs_mock(return_value):
    """Return a context-manager mock for sync DDGS whose text() returns return_value."""
    mock_instance = MagicMock()
    mock_instance.text = MagicMock(return_value=return_value)
    mock_ddgs_cls = MagicMock()
    mock_ddgs_cls.return_value.__enter__ = MagicMock(return_value=mock_instance)
    mock_ddgs_cls.return_value.__exit__ = MagicMock(return_value=None)
    return mock_ddgs_cls


def _make_ddgs_error_mock(exc):
    """Return a context-manager mock for sync DDGS that raises exc on __enter__."""
    mock_ddgs_cls = MagicMock()
    mock_ddgs_cls.return_value.__enter__ = MagicMock(side_effect=exc)
    mock_ddgs_cls.return_value.__exit__ = MagicMock(return_value=None)
    return mock_ddgs_cls


# DDGS is imported lazily inside execute(), so it is not an attribute of
# the web_search module at import time.  We must inject it into sys.modules so
# the `from duckduckgo_search import DDGS` inside execute() picks up our
# mock, rather than trying to patch a non-existent module attribute.

import sys
import types as _types


def _inject_ddgs_mock(mock_cls):
    """Inject mock_cls as duckduckgo_search.DDGS in sys.modules."""
    mod = _types.ModuleType("duckduckgo_search")
    mod.DDGS = mock_cls  # type: ignore[attr-defined]
    sys.modules["duckduckgo_search"] = mod


def _remove_ddgs_mock():
    sys.modules.pop("duckduckgo_search", None)


@pytest.mark.asyncio
async def test_web_search_execute_success():
    """execute() returns ToolResult(success=True) with normalised result dicts."""
    tool = WebSearchTool()
    mock_results = [
        {"title": "Test Title", "body": "Test snippet text", "href": "https://test.com"},
        {"title": "Second Result", "body": "Another snippet", "href": "https://example.com"},
    ]
    mock_ddgs_cls = _make_ddgs_mock(mock_results)
    _inject_ddgs_mock(mock_ddgs_cls)
    try:
        result = await tool.execute(query="test query")
    finally:
        _remove_ddgs_mock()

    assert result.success is True
    assert isinstance(result.data, list)
    assert len(result.data) == 2
    assert result.data[0]["title"] == "Test Title"
    assert result.data[0]["snippet"] == "Test snippet text"
    assert result.data[0]["url"] == "https://test.com"
    assert result.error is None


@pytest.mark.asyncio
async def test_web_search_execute_empty_results():
    """execute() handles an empty result list gracefully."""
    tool = WebSearchTool()
    mock_ddgs_cls = _make_ddgs_mock([])
    _inject_ddgs_mock(mock_ddgs_cls)
    try:
        result = await tool.execute(query="empty")
    finally:
        _remove_ddgs_mock()

    assert result.success is True
    assert result.data == []


@pytest.mark.asyncio
async def test_web_search_execute_error():
    """execute() returns ToolResult(success=False) when DDG raises an exception."""
    tool = WebSearchTool()
    mock_ddgs_cls = _make_ddgs_error_mock(RuntimeError("network error"))
    _inject_ddgs_mock(mock_ddgs_cls)
    try:
        result = await tool.execute(query="fail")
    finally:
        _remove_ddgs_mock()

    assert result.success is False
    assert result.error is not None
    assert "network error" in result.error


@pytest.mark.asyncio
async def test_web_search_execute_none_results():
    """execute() handles None return from DDG (returns empty list)."""
    tool = WebSearchTool()
    mock_ddgs_cls = _make_ddgs_mock(None)
    _inject_ddgs_mock(mock_ddgs_cls)
    try:
        result = await tool.execute(query="null-result")
    finally:
        _remove_ddgs_mock()

    assert result.success is True
    assert result.data == []


# ---------------------------------------------------------------------------
# create_default_registry
# ---------------------------------------------------------------------------


def test_create_default_registry():
    """create_default_registry() pre-loads all default tools."""
    registry = create_default_registry()
    tools = registry.get_all()
    names = {t.name for t in tools}
    expected = {
        "web_search", "web_browser", "screenshot",
        "desktop_control", "browser_control", "file_manager", "app_launcher",
        "rag_search",
    }
    assert names == expected


def test_create_default_registry_schemas():
    """Each tool from the default registry exposes a valid schema."""
    registry = create_default_registry()
    schemas = registry.get_all_schemas()
    assert len(schemas) == 8
    for schema in schemas:
        assert "name" in schema
        assert "description" in schema
        assert "parameters" in schema
