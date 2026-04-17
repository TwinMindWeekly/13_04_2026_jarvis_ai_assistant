"""Web browser tool using Playwright (headless Chromium)."""

import asyncio
import base64
import logging
from typing import ClassVar

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Maximum characters returned from page text to avoid flooding the context window.
_MAX_TEXT_CHARS = 5000
# Page-load timeout in milliseconds.
_PAGE_TIMEOUT_MS = 30_000


class WebBrowserTool(BaseTool):
    """Open a URL with a headless browser and return its text content, a screenshot, or an LLM summary.

    A single Playwright browser instance is shared across all calls (singleton
    pattern) to avoid the overhead of launching a new browser on every request.

    Actions:
        get_text   — Return raw visible page text (truncated to max_chars or _MAX_TEXT_CHARS).
        screenshot — Return a base64-encoded PNG screenshot.
        summarize  — Fetch page text and summarise it via LLM according to instructions.
                     Requires the ``instructions`` parameter to be non-empty.
    """

    name = "web_browser"
    description = (
        "Open a specific URL and read its text content, take a screenshot, or summarise "
        "the page according to instructions. "
        "Use action='summarize' with instructions to extract specific information from a page — "
        "equivalent to Grok's browse_page. "
        "Only use when you already have a URL to visit. "
        "NOT for general internet searches — use web_search instead."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to visit",
            },
            "action": {
                "type": "string",
                "enum": ["get_text", "screenshot", "summarize"],
                "description": "Action to perform (default: get_text)",
                "default": "get_text",
            },
            "instructions": {
                "type": "string",
                "description": (
                    "What to extract or summarise from the page. Required when action='summarize'. "
                    "Example: 'Extract the main pricing table as markdown'."
                ),
                "default": "",
            },
            "max_chars": {
                "type": "integer",
                "description": (
                    "Maximum characters of page text to read. Defaults to 5000 for get_text and "
                    "20000 for summarize. Increase for long-form content."
                ),
                "default": 0,
            },
        },
        "required": ["url"],
    }

    # Singleton browser / playwright handles shared across all instances.
    _playwright: ClassVar[object | None] = None
    _browser: ClassVar[object | None] = None

    # ------------------------------------------------------------------
    # Singleton browser lifecycle
    # ------------------------------------------------------------------

    async def _ensure_browser(self) -> None:
        """Launch Playwright and Chromium if not already running."""
        if WebBrowserTool._browser is not None:
            return

        logger.info("WebBrowserTool: launching Playwright Chromium browser")
        from playwright.async_api import async_playwright  # lazy import

        WebBrowserTool._playwright = await async_playwright().start()
        WebBrowserTool._browser = await WebBrowserTool._playwright.chromium.launch(  # type: ignore[union-attr]
            headless=True,
        )
        logger.info("WebBrowserTool: browser ready")

    @classmethod
    async def close_browser(cls) -> None:
        """Gracefully close the shared browser instance (call at app shutdown)."""
        if cls._browser is not None:
            await cls._browser.close()  # type: ignore[union-attr]
            cls._browser = None
        if cls._playwright is not None:
            await cls._playwright.stop()  # type: ignore[union-attr]
            cls._playwright = None
        logger.info("WebBrowserTool: browser closed")

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def execute(  # type: ignore[override]
        self,
        url: str,
        action: str = "get_text",
        instructions: str = "",
        max_chars: int = 0,
    ) -> ToolResult:
        """Navigate to *url* and return text content, a screenshot, or an LLM summary.

        Args:
            url:          The fully-qualified URL to visit.
            action:       ``"get_text"`` returns cleaned page text;
                          ``"screenshot"`` returns a base64-encoded PNG image;
                          ``"summarize"`` fetches page text and summarises via LLM.
            instructions: Required when action='summarize'. Describes what to extract.
            max_chars:    Override the character limit for page text fetching.
                          Defaults to 5000 for get_text, 20000 for summarize.

        Returns:
            ToolResult whose ``data`` field is a plain string (text/summary) or
            a base64 string (screenshot).
        """
        logger.info("WebBrowserTool executing — action=%s url=%s", action, url)

        try:
            await self._ensure_browser()

            page = await WebBrowserTool._browser.new_page()  # type: ignore[union-attr]
            try:
                await page.goto(url, timeout=_PAGE_TIMEOUT_MS, wait_until="domcontentloaded")

                if action == "screenshot":
                    png_bytes: bytes = await page.screenshot(full_page=False)
                    encoded = base64.b64encode(png_bytes).decode("utf-8")
                    logger.info("WebBrowserTool screenshot captured for %s (%d bytes)", url, len(png_bytes))
                    return ToolResult(
                        success=True,
                        data=encoded,
                        metadata={"url": url, "action": action, "format": "png/base64"},
                    )

                if action == "summarize":
                    return await self._handle_summarize(page, url, instructions, max_chars)

                # Default: get_text — extract visible text from the page body.
                char_limit = max_chars if max_chars > 0 else _MAX_TEXT_CHARS
                text: str = await page.inner_text("body")
                truncated = text[:char_limit]
                logger.info(
                    "WebBrowserTool retrieved %d chars (truncated to %d) from %s",
                    len(text),
                    len(truncated),
                    url,
                )
                return ToolResult(
                    success=True,
                    data=truncated,
                    metadata={
                        "url": url,
                        "action": action,
                        "full_length": len(text),
                        "truncated": len(text) > char_limit,
                    },
                )

            finally:
                await page.close()

        except Exception as exc:
            logger.error("WebBrowserTool failed — url=%s action=%s: %s", url, action, exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))

    async def _handle_summarize(
        self,
        page: object,
        url: str,
        instructions: str,
        max_chars: int,
    ) -> ToolResult:
        """Fetch page text and summarise it via LLM.

        Args:
            page:         Active Playwright page object.
            url:          The page URL (for prompt context).
            instructions: What to extract/summarise. Must be non-empty.
            max_chars:    Character cap for page text (default 20000 if 0).

        Returns:
            ToolResult with LLM summary as data, or raw text if LLM fails.
        """
        if not instructions or not instructions.strip():
            return ToolResult(
                success=False,
                error="instructions parameter is required for action='summarize'",
            )

        char_limit = max_chars if max_chars > 0 else 20_000

        text: str = await page.inner_text("body")  # type: ignore[union-attr]
        was_truncated = len(text) > char_limit
        page_text = text[:char_limit]
        if was_truncated:
            page_text = page_text + "\n\n[...truncated]"

        if len(text) > 10_000:
            logger.warning(
                "WebBrowserTool summarize: page is %d chars — LLM call will consume tokens (url=%s)",
                len(text),
                url,
            )

        prompt = (
            "You are extracting information from a webpage.\n"
            f"URL: {url}\n"
            f"Instructions: {instructions}\n\n"
            "Page content:\n"
            f"{page_text}\n\n"
            "Return a concise markdown response following the instructions exactly. Do not add preamble."
        )

        actual_provider = "unknown"
        actual_model = "unknown"

        try:
            from app.agent.brain import build_llm_with_fallback  # noqa: PLC0415
            from app.core.config import settings  # noqa: PLC0415
            from langchain_core.messages import HumanMessage  # noqa: PLC0415

            llm, actual_provider, actual_model = build_llm_with_fallback(
                settings.default_provider, settings.default_model
            )

            def _invoke_llm() -> str:
                response = llm.invoke([HumanMessage(content=prompt)])
                content = response.content
                # Gemini 2.5 returns list-of-dicts instead of plain string.
                if isinstance(content, list):
                    parts = [
                        b.get("text", "")
                        for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    ]
                    return "\n".join(parts)
                return str(content)

            summary: str = await asyncio.to_thread(_invoke_llm)

            logger.info(
                "WebBrowserTool summarize complete — url=%s model=%s/%s chars_in=%d",
                url, actual_provider, actual_model, len(text),
            )
            return ToolResult(
                success=True,
                data=summary,
                metadata={
                    "url": url,
                    "action": "summarize",
                    "instructions": instructions,
                    "full_length": len(text),
                    "truncated": was_truncated,
                    "model_used": f"{actual_provider}/{actual_model}",
                },
            )

        except Exception as exc:
            logger.warning(
                "WebBrowserTool summarize: LLM invocation failed for %s: %s — returning raw text",
                url, exc,
            )
            return ToolResult(
                success=True,
                data=page_text,
                metadata={
                    "url": url,
                    "action": "summarize",
                    "instructions": instructions,
                    "full_length": len(text),
                    "truncated": was_truncated,
                    "model_used": f"{actual_provider}/{actual_model}",
                    "summarization_failed": True,
                    "error": str(exc),
                },
            )
