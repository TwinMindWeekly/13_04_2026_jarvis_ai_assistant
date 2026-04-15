"""File manager tool for reading, writing, and listing files on the user's computer."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from app.tools.base import BaseTool, ToolResult
from app.tools.safety import SafetyGuard

logger = logging.getLogger(__name__)

# Maximum file size that may be read (bytes).
_MAX_READ_BYTES = 1_000_000  # 1 MB
# Maximum number of directory entries returned by a list action.
_MAX_DIR_ENTRIES = 200


def _do_file_action(action: str, path: str, content: str) -> tuple[str | None, str | None]:
    """Execute a file-system operation synchronously.

    Intended to be called via ``asyncio.to_thread`` so it never blocks the
    event loop.

    Returns:
        A ``(result, error)`` tuple.  Exactly one of the two will be None.
    """
    p = Path(path)

    if action == "read":
        if not p.exists():
            return None, f"File not found: {path}"
        if not p.is_file():
            return None, f"Path is not a file: {path}"
        if p.stat().st_size > _MAX_READ_BYTES:
            return None, f"File too large (>{_MAX_READ_BYTES // 1_000_000} MB): {path}"
        text = p.read_text(encoding="utf-8", errors="replace")
        return text, None

    elif action == "write":
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to {path}", None

    elif action == "list":
        if not p.exists():
            return None, f"Path does not exist: {path}"
        if not p.is_dir():
            return None, f"Not a directory: {path}"
        entries = sorted(p.iterdir())[:_MAX_DIR_ENTRIES]
        lines = [
            f"{'[DIR] ' if e.is_dir() else '[FILE]'} {e.name}"
            for e in entries
        ]
        return "\n".join(lines), None

    elif action == "exists":
        return str(p.exists()), None

    else:
        return None, f"Unknown action: {action}"


class FileManagerTool(BaseTool):
    """Read, write, and list files on the user's computer.

    All paths must be absolute.  Protected system paths are blocked by the
    safety guard.  Write operations require an explicit safety-level check
    (CONFIRM) before any data is modified.
    """

    name = "file_manager"
    description = (
        "Read, write, list files on the user's computer. "
        "Use absolute paths. Cannot access system-protected paths."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "list", "exists"],
                "description": "Operation to perform",
            },
            "path": {
                "type": "string",
                "description": "Absolute file or directory path",
            },
            "content": {
                "type": "string",
                "description": "Text content to write (required for write action)",
            },
        },
        "required": ["action", "path"],
    }

    async def execute(  # type: ignore[override]
        self,
        action: str,
        path: str,
        content: str = "",
        **_kwargs: Any,
    ) -> ToolResult:
        """Perform a file-system action after a safety check.

        Args:
            action:  One of read, write, list, exists.
            path:    Absolute path to the file or directory.
            content: Text to write (only relevant for action="write").

        Returns:
            ToolResult whose ``data`` is the file contents, a confirmation
            message, directory listing, or a boolean string depending on
            *action*.
        """
        logger.info("FileManagerTool executing — action=%s path=%s", action, path)

        try:
            # Safety check — write operations require CONFIRM level clearance.
            safety = SafetyGuard.check_file_path(path, write=(action == "write"))
            if not safety.allowed:
                logger.warning(
                    "FileManagerTool blocked — path=%s reason=%s", path, safety.reason
                )
                return ToolResult(success=False, error=f"Blocked: {safety.reason}")

            result, error = await asyncio.to_thread(_do_file_action, action, path, content)

            if error:
                logger.error("FileManagerTool error — action=%s path=%s: %s", action, path, error)
                return ToolResult(success=False, error=error)

            logger.info("FileManagerTool completed — action=%s path=%s", action, path)
            return ToolResult(
                success=True,
                data=result,
                metadata={"path": path, "action": action},
            )

        except Exception as exc:
            logger.error(
                "FileManagerTool failed — action=%s path=%s: %s", action, path, exc, exc_info=True
            )
            return ToolResult(success=False, error=str(exc))
