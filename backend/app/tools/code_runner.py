"""Code runner tool — execute Python, JavaScript, TypeScript, Bash, PowerShell, Godot scripts."""

import asyncio
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from app.tools.base import BaseTool, ToolResult
from app.tools.safety import SafetyGuard
from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_OUTPUT_CHARS = 50_000
_DEFAULT_TIMEOUT = 30
_MAX_TIMEOUT = 120

_LANG_CONFIG = {
    "python": {"ext": ".py", "cmd": ["python"]},
    "javascript": {"ext": ".js", "cmd": ["node"]},
    "typescript": {"ext": ".ts", "cmd": ["npx", "ts-node"]},
    "bash": {"ext": ".sh", "cmd": ["bash"]},
    "powershell": {"ext": ".ps1", "cmd": ["powershell", "-ExecutionPolicy", "Bypass", "-File"]},
    "godot": {"ext": ".gd", "cmd": None},  # uses GODOT_PATH from config
}


class CodeRunnerTool(BaseTool):
    name = "code_runner"
    description = (
        "Execute code in Python, JavaScript, TypeScript, Bash, PowerShell, or Godot GDScript. "
        "Write the code, it runs in a temp file, and stdout/stderr are returned. "
        "Use ONLY for: quick computations, testing scripts, running builds, Godot scene tests. "
        "NEVER use this for internet searches or fetching web data — use web_search instead."
    )
    parameters = {
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "enum": ["python", "javascript", "typescript", "bash", "powershell", "godot"],
                "description": "Programming language to execute",
            },
            "code": {
                "type": "string",
                "description": "Source code to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Max execution time in seconds (default 30, max 120)",
                "default": _DEFAULT_TIMEOUT,
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory (optional)",
                "default": None,
            },
            "args": {
                "type": "string",
                "description": "Command line arguments (optional)",
                "default": None,
            },
        },
        "required": ["language", "code"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        language = kwargs.get("language", "").lower()
        code = kwargs.get("code", "")
        timeout = min(kwargs.get("timeout") or _DEFAULT_TIMEOUT, _MAX_TIMEOUT)
        working_dir = kwargs.get("working_dir")
        args_str = kwargs.get("args", "")

        if not code.strip():
            return ToolResult(success=False, error="Code is required.")

        if language not in _LANG_CONFIG:
            return ToolResult(
                success=False,
                error=f"Unsupported language: {language}. Supported: {', '.join(_LANG_CONFIG.keys())}",
            )

        config = _LANG_CONFIG[language]

        # Build command
        if language == "godot":
            godot_path = settings.godot_path
            if not godot_path:
                return ToolResult(success=False, error="GODOT_PATH not configured in .env.")
            if not Path(godot_path).exists():
                return ToolResult(success=False, error=f"Godot executable not found: {godot_path}")
            cmd_base = [godot_path, "--headless", "--script"]
        else:
            cmd_base = list(config["cmd"])

        # Write code to temp file
        code_dir = Path(settings.upload_dir) / "code_runner"
        code_dir.mkdir(parents=True, exist_ok=True)

        temp_file = code_dir / f"{uuid4().hex}{config['ext']}"
        temp_file.write_text(code, encoding="utf-8")

        try:
            cmd = cmd_base + [str(temp_file)]
            if args_str:
                cmd.extend(args_str.split())

            # Safety check on the full command
            full_cmd = " ".join(cmd)
            safety = SafetyGuard.check_command(full_cmd)
            if not safety.allowed:
                return ToolResult(success=False, error=f"Blocked: {safety.reason}")

            # Validate working directory
            cwd = working_dir
            if cwd:
                cwd_path = Path(cwd)
                if not cwd_path.exists() or not cwd_path.is_dir():
                    cwd = None

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
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
                    "language": language,
                    "temp_file": str(temp_file),
                },
                error=f"Execution timed out after {timeout}s" if timed_out else None,
            )

        except Exception as exc:
            logger.exception("Code runner failed: %s", exc)
            return ToolResult(success=False, error=f"Code execution failed: {exc}")
        finally:
            # Clean up temp file (best-effort)
            try:
                temp_file.unlink(missing_ok=True)
            except Exception:
                pass
