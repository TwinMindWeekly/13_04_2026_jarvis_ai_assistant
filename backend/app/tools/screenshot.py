"""Screenshot tool using mss (cross-platform screen capture)."""

import asyncio
import base64
import io
import logging
from typing import Any

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


# Max dimension for screenshots sent to LLM. Smaller = fewer tokens.
# 1280px is enough for the LLM to understand UI layout and text.
_MAX_SCREENSHOT_WIDTH = 1280
_JPEG_QUALITY = 40  # Low quality is fine — LLM only needs to read text and see layout


def _capture_sync(region: dict[str, int] | None) -> bytes:
    """Synchronous screen capture using mss.

    Runs in a thread pool via ``asyncio.to_thread`` so it never blocks the
    event loop.  Multi-monitor captures are automatically scaled down to
    keep the base64 payload within LLM token limits.

    Args:
        region: Optional dict with keys ``left``, ``top``, ``width``,
                ``height``.  When None the full primary monitor is captured.

    Returns:
        Raw PNG bytes of the captured image.
    """
    import mss  # lazy import — only needed when the tool is called
    import mss.tools
    from PIL import Image  # Pillow for reliable PNG encoding

    with mss.mss() as sct:
        if region:
            monitor = {
                "left": region["left"],
                "top": region["top"],
                "width": region["width"],
                "height": region["height"],
            }
        else:
            # mss.monitors[1] is the primary monitor.
            # mss.monitors[0] would capture ALL monitors but is too large for LLM.
            monitor = sct.monitors[1]

        screenshot = sct.grab(monitor)

        # Convert mss ScreenShot → Pillow Image → PNG bytes.
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        # Scale down if too wide (e.g. dual 1920px monitors = 3840px total).
        if img.width > _MAX_SCREENSHOT_WIDTH:
            ratio = _MAX_SCREENSHOT_WIDTH / img.width
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
            logger.info("Screenshot resized from %dx%d to %dx%d", screenshot.size.width, screenshot.size.height, *new_size)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=_JPEG_QUALITY)
        return buffer.getvalue()


class ScreenshotTool(BaseTool):
    """Capture the screen (or a sub-region) and return a base64-encoded PNG."""

    name = "screenshot"
    description = (
        "Take a screenshot of the current screen or a specific region. "
        "Returns a base64-encoded PNG image."
    )
    parameters = {
        "type": "object",
        "properties": {
            "region": {
                "type": "object",
                "properties": {
                    "left": {"type": "integer"},
                    "top": {"type": "integer"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                },
                "description": (
                    "Optional region to capture.  "
                    "If omitted, captures the full primary screen."
                ),
            },
        },
        "required": [],
    }

    async def execute(self, region: dict[str, Any] | None = None, **_kwargs: Any) -> ToolResult:  # type: ignore[override]
        """Capture the screen and return the image as a base64 PNG string.

        Args:
            region: Optional ``{"left", "top", "width", "height"}`` dict that
                    restricts the capture area.  Pass ``None`` for full screen.

        Returns:
            ToolResult with ``data`` being a base64-encoded PNG string and
            ``metadata`` containing image dimensions.
        """
        logger.info("ScreenshotTool executing — region=%s", region)

        try:
            # mss is sync; run it in a thread to avoid blocking the event loop.
            img_bytes: bytes = await asyncio.to_thread(_capture_sync, region)

            encoded = base64.b64encode(img_bytes).decode("utf-8")

            logger.info(
                "ScreenshotTool captured %d bytes (base64 length=%d)",
                len(img_bytes),
                len(encoded),
            )
            return ToolResult(
                success=True,
                data=encoded,
                metadata={
                    "format": "jpeg/base64",
                    "size_bytes": len(img_bytes),
                    "region": region,
                },
            )

        except Exception as exc:
            logger.error("ScreenshotTool failed: %s", exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))
