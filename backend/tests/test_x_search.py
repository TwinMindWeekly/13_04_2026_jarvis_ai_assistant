"""Tests for XSearchTool in x_search.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.x_search import XSearchTool
from app.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestXSearchSchema:
    """Verify the tool schema is correctly declared."""

    def test_action_is_required(self) -> None:
        tool = XSearchTool()
        assert "action" in tool.parameters["required"]

    def test_action_enum_has_4_values(self) -> None:
        tool = XSearchTool()
        enum_values = tool.parameters["properties"]["action"]["enum"]
        assert set(enum_values) == {"keyword_search", "user_search", "thread_fetch", "semantic_search"}


# ---------------------------------------------------------------------------
# Input validation — empty required fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_search_empty_query_returns_failure() -> None:
    """keyword_search with empty query returns success=False."""
    tool = XSearchTool()
    result = await tool.execute(action="keyword_search", query="")
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_user_search_empty_username_returns_failure() -> None:
    """user_search with empty username returns success=False."""
    tool = XSearchTool()
    result = await tool.execute(action="user_search", username="")
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_thread_fetch_empty_url_returns_failure() -> None:
    """thread_fetch with empty tweet_url_or_id returns success=False."""
    tool = XSearchTool()
    result = await tool.execute(action="thread_fetch", tweet_url_or_id="")
    assert result.success is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# _extract_tweet_id static method
# ---------------------------------------------------------------------------


class TestExtractTweetId:
    """Tests for XSearchTool._extract_tweet_id."""

    def test_bare_numeric_id(self) -> None:
        assert XSearchTool._extract_tweet_id("1234567890") == "1234567890"

    def test_x_com_status_url(self) -> None:
        assert XSearchTool._extract_tweet_id(
            "https://x.com/elonmusk/status/1234567890"
        ) == "1234567890"

    def test_twitter_com_status_url_with_trailing_slash(self) -> None:
        assert XSearchTool._extract_tweet_id(
            "https://twitter.com/elonmusk/status/1234567890/"
        ) == "1234567890"

    def test_profile_url_without_status_returns_empty(self) -> None:
        assert XSearchTool._extract_tweet_id("https://x.com/elonmusk") == ""

    def test_empty_string_returns_empty(self) -> None:
        assert XSearchTool._extract_tweet_id("") == ""


# ---------------------------------------------------------------------------
# _parse_handle_from_url static method
# ---------------------------------------------------------------------------


class TestParseHandleFromUrl:
    """Tests for XSearchTool._parse_handle_from_url."""

    def test_status_url_returns_handle(self) -> None:
        assert XSearchTool._parse_handle_from_url(
            "https://x.com/elonmusk/status/123"
        ) == "elonmusk"

    def test_profile_url_returns_handle(self) -> None:
        assert XSearchTool._parse_handle_from_url(
            "https://x.com/elonmusk"
        ) == "elonmusk"

    def test_empty_string_returns_empty(self) -> None:
        assert XSearchTool._parse_handle_from_url("") == ""


# ---------------------------------------------------------------------------
# Tier 1 skip — all tiers fail → "All X/Twitter search tiers failed"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_tiers_fail_returns_descriptive_error(monkeypatch) -> None:
    """When all tiers return None, result.success=False with an informative error."""
    tool = XSearchTool()

    # Disable tier 1 by making twscrape_accounts_file empty (so _get_twscrape_api returns None).
    with patch("app.tools.x_search.XSearchTool._tier1_keyword_search", new_callable=AsyncMock, return_value=None), \
         patch("app.tools.x_search.XSearchTool._tier2_keyword_search", new_callable=AsyncMock, return_value=None), \
         patch("app.tools.x_search.XSearchTool._tier3_keyword_search", new_callable=AsyncMock, return_value=None):
        result = await tool.execute(action="keyword_search", query="python ai")

    assert result.success is False
    assert result.error is not None
    assert "All X/Twitter search tiers failed" in result.error


# ---------------------------------------------------------------------------
# Tier 3 fallback path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier3_fallback_uses_web_search_and_parses_handle() -> None:
    """Tier 3 fallback: WebSearchTool.execute is called with site=x.com; handle parsed from URL."""
    tool = XSearchTool()

    web_search_result = ToolResult(
        success=True,
        data=[
            {
                "title": "t",
                "snippet": "text",
                "url": "https://x.com/user/status/1",
                "date": None,
            }
        ],
        metadata={},
    )

    with patch("app.tools.x_search.XSearchTool._tier1_keyword_search", new_callable=AsyncMock, return_value=None), \
         patch("app.tools.x_search.XSearchTool._tier2_keyword_search", new_callable=AsyncMock, return_value=None), \
         patch("app.tools.web_search.WebSearchTool.execute", new_callable=AsyncMock, return_value=web_search_result):
        result = await tool.execute(action="keyword_search", query="test")

    assert result.success is True
    assert result.metadata["tier_used"] == 3
    assert len(result.data) == 1
    assert result.data[0]["handle"] == "user"


# ---------------------------------------------------------------------------
# thread_fetch — thread_complete=False when only tier 2 succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thread_fetch_tier2_returns_thread_complete_false() -> None:
    """thread_fetch via tier 2 sets thread_complete=False in metadata."""
    tool = XSearchTool()

    tier2_tweets = [
        {
            "author": "user",
            "handle": "user",
            "date": None,
            "text": "Root tweet",
            "url": "https://x.com/user/status/9999",
            "likes": None,
            "reposts": None,
            "score": None,
        }
    ]

    with patch("app.tools.x_search.XSearchTool._tier1_thread_fetch", new_callable=AsyncMock, return_value=None), \
         patch("app.tools.x_search.XSearchTool._tier2_keyword_search", new_callable=AsyncMock, return_value=tier2_tweets):
        result = await tool.execute(
            action="thread_fetch",
            tweet_url_or_id="https://x.com/user/status/9999",
        )

    assert result.success is True
    assert result.metadata["thread_complete"] is False
    assert result.metadata["tier_used"] == 2


# ---------------------------------------------------------------------------
# Unknown action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_action_returns_failure() -> None:
    """An unrecognised action string returns success=False with a descriptive error."""
    tool = XSearchTool()
    result = await tool.execute(action="nonexistent_action")
    assert result.success is False
    assert "nonexistent_action" in result.error or "Unknown" in result.error


# ---------------------------------------------------------------------------
# _extract_tweet_id used by tier3 for thread_fetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thread_fetch_tier3_fallback_returns_thread_complete_false() -> None:
    """thread_fetch via tier 3 (web_search) sets thread_complete=False."""
    tool = XSearchTool()

    tier3_tweets = [
        {
            "author": "user",
            "handle": "user",
            "date": None,
            "text": "Some tweet",
            "url": "https://x.com/user/status/9999",
            "likes": None,
            "reposts": None,
            "score": None,
        }
    ]

    with patch("app.tools.x_search.XSearchTool._tier1_thread_fetch", new_callable=AsyncMock, return_value=None), \
         patch("app.tools.x_search.XSearchTool._tier2_keyword_search", new_callable=AsyncMock, return_value=None), \
         patch("app.tools.x_search.XSearchTool._tier3_keyword_search", new_callable=AsyncMock, return_value=tier3_tweets):
        result = await tool.execute(
            action="thread_fetch",
            tweet_url_or_id="9999",
        )

    assert result.success is True
    assert result.metadata["thread_complete"] is False
    assert result.metadata["tier_used"] == 3
