"""Web browser tool using Playwright (headless Chromium)."""

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
    """Open a URL with a headless browser and return its text content or a screenshot.

    A single Playwright browser instance is shared across all calls (singleton
    pattern) to avoid the overhead of launching a new browser on every request.
    """

    name = "web_browser"
    description = (
        "Open a specific URL and read its text content. "
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
                "enum": ["get_text", "screenshot"],
                "description": "Action to perform (default: get_text)",
                "default": "get_text",
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

    async def execute(self, url: str, action: str = "get_text") -> ToolResult:  # type: ignore[override]
        """Navigate to *url* and return text content or a base64 PNG screenshot.

        Args:
            url:    The fully-qualified URL to visit.
            action: ``"get_text"`` (default) returns cleaned page text;
                    ``"screenshot"`` returns a base64-encoded PNG image.

        Returns:
            ToolResult whose ``data`` field is either a plain string (text) or a
            base64 string (screenshot).
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

                # Default: extract visible text from the page body.
                text: str = await page.inner_text("body")
                truncated = text[:_MAX_TEXT_CHARS]
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
                        "truncated": len(text) > _MAX_TEXT_CHARS,
                    },
                )

            finally:
                await page.close()

        except Exception as exc:
            logger.error("WebBrowserTool failed — url=%s action=%s: %s", url, action, exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))
