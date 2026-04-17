"""Clipboard tool — read/write text and images via the system clipboard."""

import asyncio
import base64
import io
import logging
import platform

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

_MAX_READ_CHARS = 50_000


class ClipboardTool(BaseTool):
    name = "clipboard"
    description = (
        "Read from or write to the system clipboard. "
        "Use 'read' to get what the user last copied (text or image). "
        "Use 'write' to put text into the clipboard. "
        "Use 'write_image' to put a base64-encoded image into the clipboard "
        "(so the user can paste it into Word, Paint, etc.). "
        "Use 'read_image' to read an image from the clipboard as base64 PNG."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "read_image", "write_image"],
                "description": "What to do with the clipboard.",
            },
            "content": {
                "type": "string",
                "description": (
                    "For 'write': the text to copy. "
                    "For 'write_image': a base64-encoded PNG/JPEG (no data URI prefix)."
                ),
                "default": None,
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        action = (kwargs.get("action") or "").lower()
        content = kwargs.get("content", "")

        if action == "read":
            return await self._read_text()
        if action == "write":
            return await self._write_text(content or "")
        if action == "read_image":
            return await self._read_image()
        if action == "write_image":
            return await self._write_image(content or "")
        return ToolResult(
            success=False,
            error=f"Unknown action: {action!r}. Use read/write/read_image/write_image.",
        )

    async def _read_text(self) -> ToolResult:
        try:
            import pyperclip  # noqa: PLC0415
            content = await asyncio.to_thread(pyperclip.paste)
            if not content:
                return ToolResult(success=True, data={"content": "", "message": "Clipboard is empty."})
            truncated = len(content) > _MAX_READ_CHARS
            if truncated:
                content = content[:_MAX_READ_CHARS]
            return ToolResult(
                success=True,
                data={"content": content, "char_count": len(content), "truncated": truncated},
            )
        except ImportError:
            return ToolResult(success=False, error="pyperclip is not installed. Run: pip install pyperclip")
        except Exception as exc:
            logger.exception("Clipboard read failed: %s", exc)
            return ToolResult(success=False, error=f"Clipboard read failed: {exc}")

    async def _write_text(self, content: str) -> ToolResult:
        if not content:
            return ToolResult(success=False, error="Content is required for write action.")
        try:
            import pyperclip  # noqa: PLC0415
            await asyncio.to_thread(pyperclip.copy, content)
            return ToolResult(
                success=True,
                data={"message": f"Copied {len(content)} characters to clipboard.", "char_count": len(content)},
            )
        except ImportError:
            return ToolResult(success=False, error="pyperclip is not installed. Run: pip install pyperclip")
        except Exception as exc:
            logger.exception("Clipboard write failed: %s", exc)
            return ToolResult(success=False, error=f"Clipboard write failed: {exc}")

    async def _read_image(self) -> ToolResult:
        """Grab an image from the clipboard and return it as base64 PNG."""
        try:
            png_bytes = await asyncio.to_thread(_grab_clipboard_image)
        except RuntimeError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            logger.exception("Clipboard image read failed: %s", exc)
            return ToolResult(success=False, error=f"Clipboard image read failed: {exc}")

        if png_bytes is None:
            return ToolResult(success=True, data={"image": None, "message": "No image in clipboard."})

        encoded = base64.b64encode(png_bytes).decode("ascii")
        return ToolResult(
            success=True,
            data={"image": encoded, "format": "png/base64", "size_bytes": len(png_bytes)},
            metadata={"size_bytes": len(png_bytes)},
        )

    async def _write_image(self, b64: str) -> ToolResult:
        """Put a base64-encoded image into the clipboard (Windows only)."""
        if not b64:
            return ToolResult(success=False, error="Image content is required for write_image.")
        if platform.system() != "Windows":
            return ToolResult(success=False, error="write_image is currently Windows-only.")

        # Strip data-URI prefix if caller included one.
        if "," in b64 and b64.lstrip().startswith("data:"):
            b64 = b64.split(",", 1)[1]

        try:
            raw = base64.b64decode(b64)
        except Exception as exc:
            return ToolResult(success=False, error=f"Invalid base64 image: {exc}")

        try:
            await asyncio.to_thread(_set_clipboard_image, raw)
        except Exception as exc:
            logger.exception("Clipboard image write failed: %s", exc)
            return ToolResult(success=False, error=f"Clipboard image write failed: {exc}")

        return ToolResult(
            success=True,
            data={"message": f"Copied image ({len(raw)} bytes) to clipboard.", "size_bytes": len(raw)},
        )


def _grab_clipboard_image() -> bytes | None:
    """Read an image off the clipboard and return PNG bytes (or None if empty).

    Uses PIL.ImageGrab which works on Windows and macOS. Linux requires xclip.
    """
    from PIL import ImageGrab  # noqa: PLC0415

    img = ImageGrab.grabclipboard()
    # On some platforms, grabclipboard returns a list of file paths instead of an image.
    if isinstance(img, list) or img is None:
        return None

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _set_clipboard_image(raw: bytes) -> None:
    """Place an image on the Windows clipboard as CF_DIB.

    We decode to PIL, re-encode as BMP, strip the 14-byte BMP header to obtain
    the DIB payload, and set CF_DIB. This is the canonical Win32 way to put
    an image on the clipboard so any app (Word, Paint, Photos…) can paste it.
    """
    try:
        import win32clipboard  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "pywin32 is required for clipboard image writes. "
            "Run `pip install pywin32` inside backend/venv and restart the server "
            "(uvicorn --reload does not re-scan installed packages, only source files)."
        ) from exc
    from PIL import Image  # noqa: PLC0415

    img = Image.open(io.BytesIO(raw))
    # Convert modes that BMP doesn't handle well.
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    with io.BytesIO() as out:
        img.convert("RGB").save(out, format="BMP")
        bmp = out.getvalue()

    # BMP file header is 14 bytes; DIB starts right after.
    dib = bmp[14:]

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib)
    finally:
        win32clipboard.CloseClipboard()
