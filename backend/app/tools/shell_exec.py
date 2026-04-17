"""Shell execution tool — run terminal commands with safety checks."""

import asyncio
import logging
from pathlib import Path

from app.tools.base import BaseTool, ToolResult
from app.tools.safety import SafetyGuard

logger = logging.getLogger(__name__)

_MAX_OUTPUT_CHARS = 50_000
_DEFAULT_TIMEOUT = 30
_MAX_TIMEOUT = 120


class ShellExecTool(BaseTool):
    name = "shell_exec"
    description = (
        "Run a shell command on the user's computer and return stdout/stderr. "
        "Use for: git, npm, pip, docker, build, test, file listing, system info. "
        "NEVER use this for internet searches or fetching web data — use web_search instead. "
        "Dangerous commands (rm -rf /, format, shutdown) are blocked."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Max seconds to wait (default 30, max 120)",
                "default": _DEFAULT_TIMEOUT,
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory (optional, defaults to user home)",
                "default": None,
            },
        },
        "required": ["command"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs.get("command", "").strip()
        timeout = min(kwargs.get("timeout") or _DEFAULT_TIMEOUT, _MAX_TIMEOUT)
        working_dir = kwargs.get("working_dir")

        if not command:
            return ToolResult(success=False, error="Command is required.")

        # Safety check
        safety = SafetyGuard.check_command(command)
        if not safety.allowed:
            return ToolResult(success=False, error=f"Blocked: {safety.reason}")

        # Validate working directory
        if working_dir:
            wd_path = Path(working_dir)
            if not wd_path.exists():
                return ToolResult(success=False, error=f"Working directory does not exist: {working_dir}")
            if not wd_path.is_dir():
                return ToolResult(success=False, error=f"Not a directory: {working_dir}")
            safety_path = SafetyGuard.check_file_path(working_dir)
            if not safety_path.allowed:
                return ToolResult(success=False, error=f"Blocked working directory: {safety_path.reason}")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            timed_out = False
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                timed_out = True
                stdout_bytes = b""
                stderr_bytes = b""

            stdout = stdout_bytes.decode("utf-8", errors="replace")[:_MAX_OUTPUT_CHARS]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[:_MAX_OUTPUT_CHARS]
            exit_code = proc.returncode or 0

            return ToolResult(
                success=not timed_out and exit_code == 0,
                data={
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": exit_code,
                    "timed_out": timed_out,
                },
                error=f"Command timed out after {timeout}s" if timed_out else None,
            )

        except Exception as exc:
            logger.exception("Shell exec failed: %s", exc)
            return ToolResult(success=False, error=f"Execution failed: {exc}")
