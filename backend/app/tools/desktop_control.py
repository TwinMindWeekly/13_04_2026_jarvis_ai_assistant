"""Desktop control tool using PyAutoGUI for mouse/keyboard automation."""

import asyncio
import base64
import io
import logging

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Maximum dimension (px) for the post-action verification screenshot.
_MAX_SCREENSHOT_DIM = 1024
# Seconds to wait after an action before capturing the verification screenshot.
_POST_ACTION_DELAY = 0.3
# Interval between key-press events when typing (seconds).
_TYPE_INTERVAL = 0.02


def _do_desktop_action(
    action: str,
    x: int,
    y: int,
    text: str,
    keys: str,
    amount: int,
) -> str:
    """Execute a single PyAutoGUI action synchronously.

    Intended to be called via ``asyncio.to_thread`` so it never blocks the
    event loop.

    Returns:
        A human-readable description of what was done.

    Raises:
        ValueError: When *action* is not recognised.
        Any PyAutoGUI / OS exception is propagated to the caller.
    """
    import pyautogui  # lazy import — optional dependency

    pyautogui.FAILSAFE = True  # moving mouse to top-left corner aborts automation

    if action == "click":
        pyautogui.click(x, y)
        return f"Clicked at ({x}, {y})"
    elif action == "double_click":
        pyautogui.doubleClick(x, y)
        return f"Double-clicked at ({x}, {y})"
    elif action == "right_click":
        pyautogui.rightClick(x, y)
        return f"Right-clicked at ({x}, {y})"
    elif action == "type":
        pyautogui.write(text, interval=_TYPE_INTERVAL)
        return f"Typed: {text[:50]}"
    elif action == "hotkey":
        parts = [k.strip() for k in keys.split("+")]
        pyautogui.hotkey(*parts)
        return f"Pressed: {keys}"
    elif action == "scroll":
        pyautogui.scroll(amount)
        return f"Scrolled {amount}"
    elif action == "move":
        pyautogui.moveTo(x, y, duration=0.2)
        return f"Moved to ({x}, {y})"
    else:
        raise ValueError(f"Unknown desktop action: {action}")


def _capture_screenshot_sync() -> str:
    """Take a screenshot with PyAutoGUI and return it as a base64 PNG string.

    Resizes to at most ``_MAX_SCREENSHOT_DIM`` on the longest side to keep
    token usage manageable.
    """
    import pyautogui  # lazy import

    screenshot = pyautogui.screenshot()
    if max(screenshot.size) > _MAX_SCREENSHOT_DIM:
        screenshot.thumbnail((_MAX_SCREENSHOT_DIM, _MAX_SCREENSHOT_DIM))
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


class DesktopControlTool(BaseTool):
    """Control the desktop via mouse clicks, keyboard input, and hotkeys.

    A post-action screenshot is always included in the result metadata so the
    LLM can verify that the action had the expected effect.

    Always take a screenshot first (using the ``screenshot`` tool) to identify
    the coordinates you need before calling this tool.
    """

    name = "desktop_control"
    description = (
        "Control the desktop: click at coordinates, type text, press hotkeys, scroll. "
        "Use this to interact with any application on the user's computer. "
        "Always take a screenshot first to see where to click."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["click", "double_click", "right_click", "type", "hotkey", "scroll", "move"],
                "description": "Action to perform",
            },
            "x": {
                "type": "integer",
                "description": "X coordinate in pixels (required for click/double_click/right_click/move)",
            },
            "y": {
                "type": "integer",
                "description": "Y coordinate in pixels (required for click/double_click/right_click/move)",
            },
            "text": {
                "type": "string",
                "description": "Text to type (required for the 'type' action)",
            },
            "keys": {
                "type": "string",
                "description": "Key combination such as 'ctrl+c' or 'alt+f4' (required for hotkey)",
            },
            "amount": {
                "type": "integer",
                "description": "Scroll clicks — positive scrolls up, negative scrolls down",
                "default": 3,
            },
        },
        "required": ["action"],
    }

    async def execute(  # type: ignore[override]
        self,
        action: str,
        x: int = 0,
        y: int = 0,
        text: str = "",
        keys: str = "",
        amount: int = 3,
    ) -> ToolResult:
        """Perform a desktop action and return a verification screenshot.

        Args:
            action: One of click, double_click, right_click, type, hotkey, scroll, move.
            x:      Target X coordinate (pixels from left edge).
            y:      Target Y coordinate (pixels from top edge).
            text:   Text string to type (only for action="type").
            keys:   Key combo like "ctrl+c" (only for action="hotkey").
            amount: Scroll amount (only for action="scroll").

        Returns:
            ToolResult whose ``metadata`` contains a base64 PNG screenshot
            taken after the action completes.
        """
        logger.info("DesktopControlTool executing — action=%s x=%d y=%d", action, x, y)

        try:
            result_msg = await asyncio.to_thread(
                _do_desktop_action, action, x, y, text, keys, amount
            )

            # Brief pause so the UI has time to react before we screenshot.
            await asyncio.sleep(_POST_ACTION_DELAY)

            screenshot_b64 = await asyncio.to_thread(_capture_screenshot_sync)

            logger.info("DesktopControlTool completed — %s", result_msg)
            return ToolResult(
                success=True,
                data=result_msg,
                metadata={"action": action, "screenshot": screenshot_b64},
            )

        except Exception as exc:
            logger.error("DesktopControlTool failed — action=%s: %s", action, exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))
