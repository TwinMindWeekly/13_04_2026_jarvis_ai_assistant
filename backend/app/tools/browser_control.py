"""Browser control tool using Playwright DOM/accessibility tree."""

import asyncio
import base64
import logging
from typing import ClassVar

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Maximum characters returned from page body text.
_MAX_TEXT_CHARS = 5000
# Page navigation timeout in milliseconds.
_NAV_TIMEOUT_MS = 30_000
# Element interaction timeout in milliseconds.
_ELEMENT_TIMEOUT_MS = 10_000
# Default browser viewport dimensions.
_VIEWPORT = {"width": 1280, "height": 800}
# Maximum entries returned from a directory listing.
_MAX_DIR_ENTRIES = 200


class BrowserControlTool(BaseTool):
    """Control a web browser via Playwright DOM and accessibility tree.

    Faster and more reliable than screenshot-based control for web pages because
    it operates directly on the page's DOM rather than pixel coordinates.

    A single Playwright browser instance is shared across all calls (singleton
    pattern) to avoid the overhead of relaunching Chromium on every request.
    """

    name = "browser_control"
    description = (
        "Control a web browser: navigate to URL, click elements by text, fill forms, "
        "extract page text. Uses DOM/accessibility tree for precision (not screenshots). "
        "Use for any web-based task."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["goto", "click_text", "fill", "get_text", "screenshot", "wait"],
                "description": "Action to perform",
            },
            "url": {
                "type": "string",
                "description": "Fully-qualified URL to navigate to (required for goto)",
            },
            "text": {
                "type": "string",
                "description": (
                    "Visible text of the element to click (click_text), "
                    "value to fill into a form field (fill), "
                    "or placeholder/label text used to locate the input (fill without selector)"
                ),
            },
            "selector": {
                "type": "string",
                "description": "CSS selector for the target element (optional alternative for fill)",
            },
            "seconds": {
                "type": "number",
                "description": "Seconds to pause (required for wait)",
                "default": 1,
            },
        },
        "required": ["action"],
    }

    # Singleton handles — shared across all instances of this class.
    _playwright: ClassVar[object | None] = None
    _browser: ClassVar[object | None] = None
    _context: ClassVar[object | None] = None
    _page: ClassVar[object | None] = None

    # ------------------------------------------------------------------
    # Singleton browser lifecycle
    # ------------------------------------------------------------------

    @classmethod
    async def _ensure_browser(cls) -> None:
        """Launch Playwright Chromium if not already running."""
        if cls._page is not None:
            return

        logger.info("BrowserControlTool: launching Playwright Chromium (headless=False)")
        from playwright.async_api import async_playwright  # lazy import

        cls._playwright = await async_playwright().start()
        cls._browser = await cls._playwright.chromium.launch(headless=False)  # type: ignore[union-attr]
        cls._context = await cls._browser.new_context(viewport=_VIEWPORT)  # type: ignore[union-attr]
        cls._page = await cls._context.new_page()  # type: ignore[union-attr]
        logger.info("BrowserControlTool: browser ready")

    @classmethod
    async def close(cls) -> None:
        """Gracefully shut down the shared browser instance (call at app shutdown)."""
        if cls._browser is not None:
            await cls._browser.close()  # type: ignore[union-attr]
            cls._browser = None
        if cls._playwright is not None:
            await cls._playwright.stop()  # type: ignore[union-attr]
            cls._playwright = None
        cls._context = None
        cls._page = None
        logger.info("BrowserControlTool: browser closed")

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def execute(  # type: ignore[override]
        self,
        action: str,
        url: str = "",
        text: str = "",
        selector: str = "",
        seconds: float = 1.0,
    ) -> ToolResult:
        """Perform a browser action and return the result.

        Args:
            action:   One of goto, click_text, fill, get_text, screenshot, wait.
            url:      Target URL (goto only).
            text:     Element text to click, form value to fill, or placeholder to
                      locate an input field.
            selector: CSS selector for the fill target (overrides text-based lookup).
            seconds:  Pause duration (wait only).

        Returns:
            ToolResult whose ``data`` contains text content, a confirmation
            message, or a base64-encoded PNG screenshot depending on *action*.
        """
        logger.info("BrowserControlTool executing — action=%s url=%s", action, url)

        try:
            await self._ensure_browser()
            page = self._page  # type: ignore[assignment]

            if action == "goto":
                await page.goto(url, timeout=_NAV_TIMEOUT_MS, wait_until="domcontentloaded")
                logger.info("BrowserControlTool navigated to %s", page.url)
                return ToolResult(
                    success=True,
                    data=f"Navigated to {url}",
                    metadata={"url": page.url},
                )

            elif action == "click_text":
                await page.get_by_text(text, exact=False).first.click(timeout=_ELEMENT_TIMEOUT_MS)
                logger.info("BrowserControlTool clicked element with text=%r", text)
                return ToolResult(
                    success=True,
                    data=f"Clicked element with text: {text}",
                )

            elif action == "fill":
                if selector:
                    await page.locator(selector).fill(text)
                else:
                    await page.get_by_placeholder(text).first.fill(text)
                logger.info("BrowserControlTool filled field selector=%r text=%r", selector, text[:50])
                return ToolResult(
                    success=True,
                    data=f"Filled with: {text[:50]}",
                )

            elif action == "get_text":
                body_text: str = await page.inner_text("body")
                truncated = body_text[:_MAX_TEXT_CHARS]
                logger.info(
                    "BrowserControlTool retrieved %d chars (truncated to %d) from %s",
                    len(body_text),
                    len(truncated),
                    page.url,
                )
                return ToolResult(
                    success=True,
                    data=truncated,
                    metadata={
                        "url": page.url,
                        "full_length": len(body_text),
                        "truncated": len(body_text) > _MAX_TEXT_CHARS,
                    },
                )

            elif action == "screenshot":
                shot_bytes: bytes = await page.screenshot(type="png")
                b64 = base64.b64encode(shot_bytes).decode("utf-8")
                logger.info(
                    "BrowserControlTool screenshot captured %d bytes from %s",
                    len(shot_bytes),
                    page.url,
                )
                return ToolResult(
                    success=True,
                    data="Screenshot captured",
                    metadata={"screenshot": b64, "url": page.url, "format": "png/base64"},
                )

            elif action == "wait":
                await asyncio.sleep(seconds)
                logger.info("BrowserControlTool waited %.1fs", seconds)
                return ToolResult(success=True, data=f"Waited {seconds}s")

            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")

        except Exception as exc:
            logger.error(
                "BrowserControlTool failed — action=%s url=%s: %s", action, url, exc, exc_info=True
            )
            return ToolResult(success=False, error=str(exc))
