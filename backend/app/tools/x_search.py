"""X/Twitter search tool with three-tier fallback: twscrape → Nitter RSS → web_search."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Output schema keys used by all tiers.
_TWEET_KEYS = ("author", "handle", "date", "text", "url", "likes", "reposts", "score")


def _empty_tweet(
    *,
    author: str = "",
    handle: str = "",
    date: str | None = None,
    text: str = "",
    url: str = "",
    likes: int | None = None,
    reposts: int | None = None,
    score: float | None = None,
) -> dict[str, Any]:
    """Build a tweet result dict with the canonical output schema."""
    return {
        "author": author,
        "handle": handle,
        "date": date,
        "text": text,
        "url": url,
        "likes": likes,
        "reposts": reposts,
        "score": score,
    }


class XSearchTool(BaseTool):
    """Search X/Twitter content via a three-tier fallback strategy.

    Tier 1 — twscrape (requires account pool DB file configured via
              TWSCRAPE_ACCOUNTS_FILE env var / settings.twscrape_accounts_file).
    Tier 2 — Nitter RSS feeds (public instances, may be rate-limited or down).
    Tier 3 — DuckDuckGo web_search with site:x.com operator (last resort).

    X/Twitter scraping is best-effort — instances may fail, rate-limit, or block.
    Prefer configuring twscrape accounts for reliability.

    Always includes metadata.tier_used (1 | 2 | 3) so the caller knows data reliability.
    """

    name = "x_search"
    description = (
        "Search X/Twitter for tweets, user timelines, and threads. "
        "X/Twitter scraping is best-effort — instances may fail, rate-limit, or block. "
        "Prefer configuring twscrape accounts for reliability. "
        "Actions: keyword_search (search by query), user_search (user timeline), "
        "thread_fetch (full reply thread — requires twscrape), "
        "semantic_search (keyword search + embedding rerank). "
        "Returns tweets with author, handle, date, text, url, likes, reposts."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["keyword_search", "user_search", "thread_fetch", "semantic_search"],
                "description": "Action to perform",
            },
            "query": {
                "type": "string",
                "description": "Search query. Required for keyword_search and semantic_search.",
                "default": "",
            },
            "username": {
                "type": "string",
                "description": "Twitter/X username (without @). Required for user_search.",
                "default": "",
            },
            "tweet_url_or_id": {
                "type": "string",
                "description": "Tweet URL or numeric tweet ID. Required for thread_fetch.",
                "default": "",
            },
            "since": {
                "type": "string",
                "description": "Start date filter, ISO format e.g. '2026-01-01'.",
                "default": "",
            },
            "until": {
                "type": "string",
                "description": "End date filter, ISO format e.g. '2026-04-17'.",
                "default": "",
            },
            "filter_type": {
                "type": "string",
                "enum": ["images", "videos", "links", "replies", "verified"],
                "description": "Optional tweet filter type.",
                "default": "",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of tweets to return.",
                "default": 10,
            },
        },
        "required": ["action"],
    }

    # ------------------------------------------------------------------
    # execute() — top-level dispatcher
    # ------------------------------------------------------------------

    async def execute(  # type: ignore[override]
        self,
        action: str,
        query: str = "",
        username: str = "",
        tweet_url_or_id: str = "",
        since: str = "",
        until: str = "",
        filter_type: str = "",
        limit: int = 10,
    ) -> ToolResult:
        """Dispatch to the requested action with three-tier fallback.

        Args:
            action:           One of keyword_search, user_search, thread_fetch, semantic_search.
            query:            Search query (keyword_search / semantic_search).
            username:         Twitter handle without @ (user_search).
            tweet_url_or_id:  Tweet URL or ID string (thread_fetch).
            since:            ISO date filter start.
            until:            ISO date filter end.
            filter_type:      Optional tweet filter (images/videos/links/replies/verified).
            limit:            Maximum results to return.

        Returns:
            ToolResult with list of tweet dicts, or error on total failure.
        """
        try:
            if action == "keyword_search":
                return await self._keyword_search(
                    query=query, since=since, until=until,
                    filter_type=filter_type, limit=limit,
                )
            if action == "user_search":
                return await self._user_search(username=username, limit=limit)
            if action == "thread_fetch":
                return await self._thread_fetch(tweet_url_or_id=tweet_url_or_id)
            if action == "semantic_search":
                return await self._semantic_search(
                    query=query, since=since, until=until,
                    filter_type=filter_type, limit=limit,
                )
            return ToolResult(
                success=False,
                error=f"Unknown action: {action!r}. Must be one of: keyword_search, user_search, thread_fetch, semantic_search",
            )
        except Exception as exc:
            logger.error("XSearchTool unhandled error — action=%s: %s", action, exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    async def _keyword_search(
        self,
        query: str,
        since: str,
        until: str,
        filter_type: str,
        limit: int,
    ) -> ToolResult:
        """Search tweets by keyword with date/filter operators."""
        if not query:
            return ToolResult(success=False, error="query is required for keyword_search")

        # Tier 1 — twscrape
        tier1_result = await self._tier1_keyword_search(query, since, until, filter_type, limit)
        if tier1_result is not None:
            return ToolResult(
                success=True,
                data=tier1_result,
                metadata={"action": "keyword_search", "query": query, "tier_used": 1},
            )

        # Tier 2 — Nitter RSS
        tier2_result = await self._tier2_keyword_search(query, since, until, filter_type, limit)
        if tier2_result is not None:
            return ToolResult(
                success=True,
                data=tier2_result,
                metadata={"action": "keyword_search", "query": query, "tier_used": 2},
            )

        # Tier 3 — web_search fallback
        tier3_result = await self._tier3_keyword_search(query, since, until, filter_type, limit)
        if tier3_result is not None:
            return ToolResult(
                success=True,
                data=tier3_result,
                metadata={
                    "action": "keyword_search",
                    "query": query,
                    "tier_used": 3,
                    "warning": "Using web_search site:x.com fallback — engagement counts unavailable",
                },
            )

        return ToolResult(
            success=False,
            error=(
                "All X/Twitter search tiers failed. "
                "To enable twscrape, set TWSCRAPE_ACCOUNTS_FILE to a valid twscrape SQLite DB. "
                "Nitter public instances may be down. "
                "Try again later or use web_search with site:x.com directly."
            ),
        )

    async def _user_search(self, username: str, limit: int) -> ToolResult:
        """Return recent tweets from a user's timeline."""
        if not username:
            return ToolResult(success=False, error="username is required for user_search")

        handle = username.lstrip("@")

        # Tier 1 — twscrape
        tier1_result = await self._tier1_user_search(handle, limit)
        if tier1_result is not None:
            return ToolResult(
                success=True,
                data=tier1_result,
                metadata={"action": "user_search", "username": handle, "tier_used": 1},
            )

        # Tier 2 — Nitter RSS
        tier2_result = await self._tier2_user_search(handle, limit)
        if tier2_result is not None:
            return ToolResult(
                success=True,
                data=tier2_result,
                metadata={"action": "user_search", "username": handle, "tier_used": 2},
            )

        # Tier 3 — web_search fallback
        tier3_result = await self._tier3_keyword_search(
            query=f"from:{handle}", since="", until="", filter_type="", limit=limit
        )
        if tier3_result is not None:
            return ToolResult(
                success=True,
                data=tier3_result,
                metadata={
                    "action": "user_search",
                    "username": handle,
                    "tier_used": 3,
                    "warning": "Using web_search site:x.com fallback — engagement counts unavailable",
                },
            )

        return ToolResult(
            success=False,
            error=(
                f"Could not retrieve timeline for @{handle}. "
                "Nitter instances may be down. Configure twscrape for reliable access."
            ),
        )

    async def _thread_fetch(self, tweet_url_or_id: str) -> ToolResult:
        """Fetch a tweet thread. Only tier 1 (twscrape) supports full threads."""
        if not tweet_url_or_id:
            return ToolResult(success=False, error="tweet_url_or_id is required for thread_fetch")

        # Tier 1 — twscrape (only tier that can fetch full threads)
        tier1_result = await self._tier1_thread_fetch(tweet_url_or_id)
        if tier1_result is not None:
            return ToolResult(
                success=True,
                data=tier1_result,
                metadata={
                    "action": "thread_fetch",
                    "tweet_url_or_id": tweet_url_or_id,
                    "tier_used": 1,
                    "thread_complete": True,
                },
            )

        # Tier 2/3 — can only return the root tweet
        tweet_id = self._extract_tweet_id(tweet_url_or_id)
        root_url = f"https://x.com/i/web/status/{tweet_id}" if tweet_id else tweet_url_or_id
        query = f"url:{root_url}" if tweet_id else tweet_url_or_id

        tier2_result = await self._tier2_keyword_search(query, "", "", "", 1)
        if tier2_result:
            return ToolResult(
                success=True,
                data=tier2_result,
                metadata={
                    "action": "thread_fetch",
                    "tweet_url_or_id": tweet_url_or_id,
                    "tier_used": 2,
                    "thread_complete": False,
                    "note": "Full thread requires twscrape — only root tweet returned",
                },
            )

        tier3_result = await self._tier3_keyword_search(tweet_url_or_id, "", "", "", 1)
        if tier3_result:
            return ToolResult(
                success=True,
                data=tier3_result,
                metadata={
                    "action": "thread_fetch",
                    "tweet_url_or_id": tweet_url_or_id,
                    "tier_used": 3,
                    "thread_complete": False,
                    "note": "Full thread requires twscrape — only root tweet returned via web_search",
                },
            )

        return ToolResult(
            success=False,
            error=(
                "Could not fetch thread. Configure twscrape for reliable thread access. "
                "Set TWSCRAPE_ACCOUNTS_FILE to a valid twscrape SQLite DB."
            ),
        )

    async def _semantic_search(
        self,
        query: str,
        since: str,
        until: str,
        filter_type: str,
        limit: int,
    ) -> ToolResult:
        """Keyword search with embedding-based reranking."""
        if not query:
            return ToolResult(success=False, error="query is required for semantic_search")

        # Fetch a larger pool then rerank.
        pool_result = await self._keyword_search(
            query=query, since=since, until=until,
            filter_type=filter_type, limit=limit * 3,
        )

        if not pool_result.success or not pool_result.data:
            # Propagate failure or empty result with updated action name.
            return ToolResult(
                success=pool_result.success,
                data=pool_result.data,
                error=pool_result.error,
                metadata={**pool_result.metadata, "action": "semantic_search"},
            )

        tweets: list[dict[str, Any]] = pool_result.data

        try:
            from app.tools._search_helpers import rerank_results  # noqa: PLC0415

            def _text_fn(t: dict[str, Any]) -> str:
                return t.get("text", "")

            reranked = await asyncio.to_thread(rerank_results, query, tweets, _text_fn, limit)
        except Exception as exc:
            logger.warning("XSearchTool semantic_search rerank failed: %s — returning raw results", exc)
            reranked = tweets[:limit]

        return ToolResult(
            success=True,
            data=reranked,
            metadata={
                **pool_result.metadata,
                "action": "semantic_search",
                "reranked": True,
            },
        )

    # ------------------------------------------------------------------
    # Tier 1 — twscrape
    # ------------------------------------------------------------------

    def _get_twscrape_api(self) -> object | None:
        """Instantiate twscrape API if available and accounts DB is configured.

        Returns the API object on success, or None if twscrape is unavailable.
        """
        try:
            from twscrape import API  # noqa: PLC0415
        except ImportError:
            logger.debug("twscrape not installed — skipping tier 1")
            return None

        try:
            from app.core.config import settings  # noqa: PLC0415

            db_path = settings.twscrape_accounts_file
            if not db_path or not Path(db_path).exists():
                logger.debug("twscrape_accounts_file not set or missing — skipping tier 1")
                return None

            return API(db_path)
        except Exception as exc:
            logger.debug("twscrape API init failed: %s", exc)
            return None

    def _twscrape_tweet_to_dict(self, tweet: object) -> dict[str, Any]:
        """Convert a twscrape Tweet object to the canonical output dict."""
        handle = getattr(getattr(tweet, "user", None), "username", "") or ""
        author = getattr(getattr(tweet, "user", None), "displayname", "") or handle
        tweet_id = getattr(tweet, "id", None)
        url = f"https://x.com/{handle}/status/{tweet_id}" if handle and tweet_id else ""
        date_obj = getattr(tweet, "date", None)
        date_str = date_obj.isoformat() if date_obj is not None else None
        return _empty_tweet(
            author=author,
            handle=handle,
            date=date_str,
            text=getattr(tweet, "rawContent", "") or "",
            url=url,
            likes=getattr(tweet, "likeCount", None),
            reposts=getattr(tweet, "retweetCount", None),
        )

    def _build_twscrape_query(
        self,
        query: str,
        since: str,
        until: str,
        filter_type: str,
    ) -> str:
        """Build a Twitter advanced search query string for twscrape."""
        parts = [query]
        if since:
            parts.append(f"since:{since}")
        if until:
            parts.append(f"until:{until}")
        if filter_type:
            parts.append(f"filter:{filter_type}")
        return " ".join(parts)

    async def _tier1_keyword_search(
        self,
        query: str,
        since: str,
        until: str,
        filter_type: str,
        limit: int,
    ) -> list[dict[str, Any]] | None:
        """Tier 1 keyword search via twscrape."""
        api = self._get_twscrape_api()
        if api is None:
            return None

        try:
            from twscrape import gather  # noqa: PLC0415

            q = self._build_twscrape_query(query, since, until, filter_type)
            tweets = await gather(api.search(q, limit=limit))
            results = [self._twscrape_tweet_to_dict(t) for t in tweets]
            logger.info("XSearchTool tier1 keyword_search: %d tweets for %r", len(results), q)
            return results if results else None
        except Exception as exc:
            logger.warning("XSearchTool tier1 keyword_search failed: %s", exc)
            return None

    async def _tier1_user_search(self, handle: str, limit: int) -> list[dict[str, Any]] | None:
        """Tier 1 user timeline via twscrape."""
        api = self._get_twscrape_api()
        if api is None:
            return None

        try:
            from twscrape import gather  # noqa: PLC0415

            tweets = await gather(api.user_tweets(handle, limit=limit))
            results = [self._twscrape_tweet_to_dict(t) for t in tweets]
            logger.info("XSearchTool tier1 user_search: %d tweets for @%s", len(results), handle)
            return results if results else None
        except Exception as exc:
            logger.warning("XSearchTool tier1 user_search failed: %s", exc)
            return None

    async def _tier1_thread_fetch(self, tweet_url_or_id: str) -> list[dict[str, Any]] | None:
        """Tier 1 thread fetch via twscrape.

        Note: Uses api.tweet_replies() which may not exist in all twscrape versions.
        If this method is missing, tier 1 thread_fetch will fail gracefully and fall
        through to tier 2/3. Check twscrape release notes for the correct method name.
        """
        api = self._get_twscrape_api()
        if api is None:
            return None

        tweet_id = self._extract_tweet_id(tweet_url_or_id)
        if not tweet_id:
            logger.warning("XSearchTool tier1 thread_fetch: cannot parse tweet ID from %r", tweet_url_or_id)
            return None

        try:
            from twscrape import gather  # noqa: PLC0415

            # tweet_replies is the best-effort method; fall back gracefully if absent.
            fetch_fn = getattr(api, "tweet_replies", None)
            if fetch_fn is None:
                logger.warning("XSearchTool tier1: twscrape has no tweet_replies method — skipping tier 1")
                return None

            tweets = await gather(fetch_fn(int(tweet_id), limit=100))
            results = [self._twscrape_tweet_to_dict(t) for t in tweets]
            logger.info("XSearchTool tier1 thread_fetch: %d tweets for id=%s", len(results), tweet_id)
            return results if results else None
        except Exception as exc:
            logger.warning("XSearchTool tier1 thread_fetch failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Tier 2 — Nitter RSS
    # ------------------------------------------------------------------

    async def _tier2_keyword_search(
        self,
        query: str,
        since: str,
        until: str,
        filter_type: str,
        limit: int,
    ) -> list[dict[str, Any]] | None:
        """Tier 2 keyword search via Nitter RSS."""
        try:
            import feedparser  # noqa: PLC0415
            import httpx  # noqa: PLC0415
        except ImportError as exc:
            logger.debug("feedparser/httpx not available for Nitter tier: %s", exc)
            return None

        from app.core.config import settings  # noqa: PLC0415

        instances = list(settings.x_nitter_instances)

        for instance in instances:
            try:
                url = f"{instance.rstrip('/')}/search/rss?q={query}"
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    response = await client.get(url)
                    if response.status_code != 200:
                        continue

                def _parse(content: str) -> list[dict[str, Any]]:
                    feed = feedparser.parse(content)
                    items: list[dict[str, Any]] = []
                    for entry in feed.entries[:limit]:
                        author = getattr(entry, "author", "") or ""
                        handle = author.lstrip("@")
                        link = getattr(entry, "link", "") or ""
                        # Convert nitter link to x.com canonical link
                        x_link = link.replace(instance.rstrip("/"), "https://x.com") if link else link
                        published = getattr(entry, "published", None)
                        items.append(_empty_tweet(
                            author=author,
                            handle=handle,
                            date=published,
                            text=getattr(entry, "title", "") or "",
                            url=x_link,
                        ))
                    return items

                results = await asyncio.to_thread(_parse, response.text)
                if results:
                    logger.info(
                        "XSearchTool tier2 keyword_search: %d results via %s", len(results), instance
                    )
                    return results
            except Exception as exc:
                logger.debug("XSearchTool Nitter instance %s failed: %s", instance, exc)
                continue

        logger.warning("XSearchTool tier2 keyword_search: all Nitter instances failed for query=%r", query)
        return None

    async def _tier2_user_search(self, handle: str, limit: int) -> list[dict[str, Any]] | None:
        """Tier 2 user timeline via Nitter RSS."""
        try:
            import feedparser  # noqa: PLC0415
            import httpx  # noqa: PLC0415
        except ImportError as exc:
            logger.debug("feedparser/httpx not available for Nitter tier: %s", exc)
            return None

        from app.core.config import settings  # noqa: PLC0415

        instances = list(settings.x_nitter_instances)

        for instance in instances:
            try:
                url = f"{instance.rstrip('/')}/{handle}/rss"
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    response = await client.get(url)
                    if response.status_code != 200:
                        continue

                def _parse(content: str) -> list[dict[str, Any]]:
                    feed = feedparser.parse(content)
                    items: list[dict[str, Any]] = []
                    for entry in feed.entries[:limit]:
                        author = getattr(entry, "author", "") or handle
                        link = getattr(entry, "link", "") or ""
                        x_link = link.replace(instance.rstrip("/"), "https://x.com") if link else link
                        published = getattr(entry, "published", None)
                        items.append(_empty_tweet(
                            author=author,
                            handle=handle,
                            date=published,
                            text=getattr(entry, "title", "") or "",
                            url=x_link,
                        ))
                    return items

                results = await asyncio.to_thread(_parse, response.text)
                if results:
                    logger.info(
                        "XSearchTool tier2 user_search: %d results via %s for @%s", len(results), instance, handle
                    )
                    return results
            except Exception as exc:
                logger.debug("XSearchTool Nitter instance %s user_search failed: %s", instance, exc)
                continue

        logger.warning("XSearchTool tier2 user_search: all Nitter instances failed for @%s", handle)
        return None

    # ------------------------------------------------------------------
    # Tier 3 — web_search with site:x.com
    # ------------------------------------------------------------------

    async def _tier3_keyword_search(
        self,
        query: str,
        since: str,
        until: str,
        filter_type: str,
        limit: int,
    ) -> list[dict[str, Any]] | None:
        """Tier 3 fallback: DuckDuckGo web_search with site:x.com."""
        try:
            from app.tools.web_search import WebSearchTool  # noqa: PLC0415

            logger.warning(
                "XSearchTool: falling back to tier 3 (web_search site:x.com) for query=%r", query
            )

            augmented_query = query
            if since:
                augmented_query = f"{augmented_query} since:{since}"
            if until:
                augmented_query = f"{augmented_query} until:{until}"

            ws_result = await WebSearchTool().execute(
                query=augmented_query,
                site="x.com",
                num_results=limit,
            )

            if not ws_result.success or not ws_result.data:
                return None

            tweets: list[dict[str, Any]] = []
            for item in ws_result.data:
                url: str = item.get("url", "")
                handle = self._parse_handle_from_url(url)
                tweets.append(_empty_tweet(
                    author=handle,
                    handle=handle,
                    date=item.get("date"),
                    text=item.get("snippet", "") or item.get("title", ""),
                    url=url,
                ))

            logger.info("XSearchTool tier3: %d results via web_search site:x.com", len(tweets))
            return tweets if tweets else None

        except Exception as exc:
            logger.warning("XSearchTool tier3 fallback failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_tweet_id(tweet_url_or_id: str) -> str:
        """Extract numeric tweet ID from a URL or return the bare ID string."""
        s = tweet_url_or_id.strip()
        if s.isdigit():
            return s
        # URL pattern: https://x.com/<handle>/status/<id> or twitter.com variant
        parts = s.rstrip("/").split("/")
        for i, part in enumerate(parts):
            if part == "status" and i + 1 < len(parts) and parts[i + 1].isdigit():
                return parts[i + 1]
        return ""

    @staticmethod
    def _parse_handle_from_url(url: str) -> str:
        """Parse @handle from an x.com / twitter.com URL."""
        try:
            parts = url.rstrip("/").split("/")
            # https://x.com/<handle>/status/<id>  →  index -3 is handle
            if "status" in parts:
                idx = parts.index("status")
                if idx > 0:
                    return parts[idx - 1]
            # https://x.com/<handle>
            if len(parts) >= 4:
                return parts[3]
        except Exception:
            pass
        return ""
