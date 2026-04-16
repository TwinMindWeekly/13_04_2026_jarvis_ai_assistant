"""Clipboard tool — read from and write to the system clipboard."""

import asyncio
import logging

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

_MAX_READ_CHARS = 50_000


class ClipboardTool(BaseTool):
    name = "clipboard"
    description = (
        "Read from or write to the system clipboard. "
        "Use 'read' to get what the user last copied. "
        "Use 'write' to put text into the clipboard for the user to paste."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write"],
                "description": "Read from or write to clipboard",
            },
            "content": {
                "type": "string",
                "description": "Text to write to clipboard (required for 'write' action)",
                "default": None,
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "").lower()

        if action == "read":
            return await self._read()
        if action == "write":
            return await self._write(kwargs.get("content", ""))
        return ToolResult(success=False, error=f"Unknown action: {action}. Use 'read' or 'write'.")

    async def _read(self) -> ToolResult:
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

    async def _write(self, content: str) -> ToolResult:
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
