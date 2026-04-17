"""Tests for WebSearchTool and _build_query in web_search.py."""

import sys
import types as _types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.web_search import WebSearchTool, _build_query
from app.tools._search_helpers import build_query


# ---------------------------------------------------------------------------
# DDGS mock helpers (mirrors the pattern in test_tools.py lines 184-215)
# ---------------------------------------------------------------------------


def _make_ddgs_mock(return_value, *, capture: bool = False):
    """Return (mock_cls, mock_instance) for DDGS.

    When *capture* is True, returns the pair so callers can assert on
    mock_instance.text.call_args.
    """
    mock_instance = MagicMock()
    mock_instance.text = MagicMock(return_value=return_value)
    mock_cls = MagicMock(return_value=mock_instance)
    if capture:
        return mock_cls, mock_instance
    return mock_cls


def _inject_ddgs_mock(mock_cls) -> None:
    """Inject mock_cls as ddgs.DDGS into sys.modules."""
    mod = _types.ModuleType("ddgs")
    mod.DDGS = mock_cls  # type: ignore[attr-defined]
    sys.modules["ddgs"] = mod


def _remove_ddgs_mock() -> None:
    sys.modules.pop("ddgs", None)


# ---------------------------------------------------------------------------
# _build_query / build_query — pure function tests (no I/O)
# ---------------------------------------------------------------------------


class TestBuildQuery:
    """Tests for the _build_query / build_query pure helper."""

    def test_no_operators_returns_query_unchanged(self) -> None:
        result = _build_query("python async")
        assert result == "python async"

    def test_site_operator(self) -> None:
        result = _build_query("flask", site="github.com")
        assert result == "flask site:github.com"

    def test_exact_phrase_operator(self) -> None:
        result = _build_query("test", exact_phrase="hello world")
        assert result == 'test "hello world"'

    def test_exclude_operator(self) -> None:
        result = _build_query("results", exclude=["spam", "ads"])
        assert "-spam" in result
        assert "-ads" in result
        assert result.startswith("results")

    def test_filetype_operator(self) -> None:
        result = _build_query("report", filetype="pdf")
        assert result == "report filetype:pdf"

    def test_all_operators_combined(self) -> None:
        result = _build_query(
            "test",
            site="github.com",
            exact_phrase="hello",
            exclude=["spam"],
            filetype="pdf",
        )
        assert result == 'test site:github.com "hello" -spam filetype:pdf'

    def test_strips_whitespace_from_query(self) -> None:
        result = _build_query("  python  ")
        assert result == "python"

    def test_strips_whitespace_from_site(self) -> None:
        result = _build_query("q", site="  github.com  ")
        assert result == "q site:github.com"

    def test_strips_whitespace_from_exact_phrase(self) -> None:
        result = _build_query("q", exact_phrase="  hello  ")
        assert result == 'q "hello"'

    def test_skips_empty_strings_in_exclude(self) -> None:
        result = _build_query("q", exclude=["spam", "", "  ", "ads"])
        assert "-spam" in result
        assert "-ads" in result
        # empty / blank entries must not produce stray '-' tokens
        parts = result.split()
        assert "-" not in parts
        assert all(p != "-" for p in parts)

    def test_build_query_helper_mirrors_build_query(self) -> None:
        """_build_query is a thin wrapper around build_query — results must match."""
        kwargs = dict(site="x.com", exact_phrase="hello", exclude=["noise"], filetype="pdf")
        assert _build_query("q", **kwargs) == build_query("q", **kwargs)

    def test_empty_exclude_list(self) -> None:
        result = _build_query("q", exclude=[])
        assert result == "q"

    def test_none_exclude(self) -> None:
        result = _build_query("q", exclude=None)
        assert result == "q"


# ---------------------------------------------------------------------------
# WebSearchTool.execute — new parameter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_site_param_augments_query() -> None:
    """site='x.com' makes DDGS receive an augmented query containing site:x.com."""
    tool = WebSearchTool()
    mock_cls, mock_instance = _make_ddgs_mock([], capture=True)
    _inject_ddgs_mock(mock_cls)
    try:
        result = await tool.execute(query="python", site="x.com")
    finally:
        _remove_ddgs_mock()

    assert result.success is True
    called_query = mock_instance.text.call_args.args[0]
    assert "site:x.com" in called_query
    assert result.metadata["augmented_query"] == "python site:x.com"


@pytest.mark.asyncio
async def test_execute_date_range_passes_timelimit() -> None:
    """date_range='w' passes timelimit='w' kwarg to DDGS.text()."""
    tool = WebSearchTool()
    mock_cls, mock_instance = _make_ddgs_mock([], capture=True)
    _inject_ddgs_mock(mock_cls)
    try:
        await tool.execute(query="news", date_range="w")
    finally:
        _remove_ddgs_mock()

    assert mock_instance.text.call_args.kwargs.get("timelimit") == "w"


@pytest.mark.asyncio
async def test_execute_region_passes_region_kwarg() -> None:
    """region='us-en' passes region='us-en' kwarg to DDGS.text()."""
    tool = WebSearchTool()
    mock_cls, mock_instance = _make_ddgs_mock([], capture=True)
    _inject_ddgs_mock(mock_cls)
    try:
        await tool.execute(query="news", region="us-en")
    finally:
        _remove_ddgs_mock()

    assert mock_instance.text.call_args.kwargs.get("region") == "us-en"


@pytest.mark.asyncio
async def test_execute_safe_search_passes_safesearch_kwarg() -> None:
    """safe_search='off' passes safesearch='off' kwarg to DDGS.text()."""
    tool = WebSearchTool()
    mock_cls, mock_instance = _make_ddgs_mock([], capture=True)
    _inject_ddgs_mock(mock_cls)
    try:
        await tool.execute(query="news", safe_search="off")
    finally:
        _remove_ddgs_mock()

    assert mock_instance.text.call_args.kwargs.get("safesearch") == "off"


@pytest.mark.asyncio
async def test_execute_date_field_in_output() -> None:
    """When DDGS result includes a 'date' key, output dict includes 'date'."""
    tool = WebSearchTool()
    raw = [
        {
            "title": "Article",
            "body": "Snippet",
            "href": "https://example.com",
            "date": "2026-04-01",
        }
    ]
    mock_cls = _make_ddgs_mock(raw)
    _inject_ddgs_mock(mock_cls)
    try:
        result = await tool.execute(query="test")
    finally:
        _remove_ddgs_mock()

    assert result.success is True
    assert result.data[0].get("date") == "2026-04-01"


@pytest.mark.asyncio
async def test_execute_metadata_fields() -> None:
    """metadata includes augmented_query and reranked fields."""
    tool = WebSearchTool()
    mock_cls = _make_ddgs_mock([{"title": "T", "body": "S", "href": "https://a.com"}])
    _inject_ddgs_mock(mock_cls)
    try:
        result = await tool.execute(query="hello", site="github.com")
    finally:
        _remove_ddgs_mock()

    assert result.success is True
    assert "augmented_query" in result.metadata
    assert "reranked" in result.metadata
    assert result.metadata["reranked"] is False


# ---------------------------------------------------------------------------
# Rerank path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rerank_fetches_3x_results() -> None:
    """When rerank=True, DDGS is called with max_results = num_results * 3."""
    tool = WebSearchTool()
    mock_cls, mock_instance = _make_ddgs_mock([], capture=True)
    _inject_ddgs_mock(mock_cls)
    try:
        await tool.execute(query="python", num_results=5, rerank=True)
    finally:
        _remove_ddgs_mock()

    assert mock_instance.text.call_args.kwargs.get("max_results") == 15


@pytest.mark.asyncio
async def test_rerank_calls_rerank_results_and_adds_score() -> None:
    """When rerank=True, rerank_results is called and output items have 'score' key."""
    tool = WebSearchTool()
    raw_ddgs = [
        {"title": f"T{i}", "body": f"S{i}", "href": f"https://example.com/{i}"}
        for i in range(6)
    ]
    mock_cls = _make_ddgs_mock(raw_ddgs)
    _inject_ddgs_mock(mock_cls)

    scored_items = [
        {"title": "T0", "snippet": "S0", "url": "https://example.com/0", "score": 0.95},
        {"title": "T3", "snippet": "S3", "url": "https://example.com/3", "score": 0.88},
    ]

    try:
        with patch("app.tools.web_search.rerank_results", return_value=scored_items) as mock_rerank:
            result = await tool.execute(query="python", num_results=2, rerank=True)
    finally:
        _remove_ddgs_mock()

    assert result.success is True
    mock_rerank.assert_called_once()
    assert all("score" in item for item in result.data)
    assert result.metadata["reranked"] is True


@pytest.mark.asyncio
async def test_rerank_false_does_not_call_rerank_results() -> None:
    """When rerank=False, rerank_results is never called."""
    tool = WebSearchTool()
    mock_cls = _make_ddgs_mock([{"title": "T", "body": "S", "href": "https://a.com"}])
    _inject_ddgs_mock(mock_cls)
    try:
        with patch("app.tools.web_search.rerank_results") as mock_rerank:
            result = await tool.execute(query="python", rerank=False)
    finally:
        _remove_ddgs_mock()

    mock_rerank.assert_not_called()
    assert result.success is True
