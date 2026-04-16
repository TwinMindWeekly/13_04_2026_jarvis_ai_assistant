"""App launcher tool — opens applications on the host OS.

Supports whitelisted names and auto-resolves executables via PATH / registry
when the exact name isn't in the whitelist.
"""

import asyncio
import logging
import os
import platform
import subprocess
from typing import Any

from app.tools.base import BaseTool, ToolResult
from app.tools.safety import SafetyGuard

logger = logging.getLogger(__name__)

# Maps friendly user-facing names to the executable name used on each OS.
_APP_COMMANDS: dict[str, str] = {
    "notepad": "notepad",
    "calc": "calc",
    "calculator": "calc",
    "chrome": "chrome",
    "edge": "msedge",
    "msedge": "msedge",
    "firefox": "firefox",
    "code": "code",
    "vscode": "code",
    "explorer": "explorer",
    "cmd": "cmd",
    "powershell": "powershell",
}


def _find_executable(name: str) -> str | None:
    """Try to find the full path of an executable on the system.

    Uses `where` on Windows, `which` on POSIX. Returns the first match
    or None if not found.
    """
    os_name = platform.system()
    try:
        if os_name == "Windows":
            result = subprocess.run(
                ["where", name],
                capture_output=True, text=True, timeout=5,
            )
        else:
            result = subprocess.run(
                ["which", name],
                capture_output=True, text=True, timeout=5,
            )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def _find_windows_app(name: str) -> str | None:
    """Search common Windows install locations and Start Menu shortcuts."""
    name_lower = name.lower()

    # Check common paths for popular apps
    common_paths = [
        os.path.expandvars(r"%ProgramFiles%"),
        os.path.expandvars(r"%ProgramFiles(x86)%"),
        os.path.expandvars(r"%LocalAppData%\Programs"),
        os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
    ]

    for base in common_paths:
        if not os.path.isdir(base):
            continue
        try:
            for root, _dirs, files in os.walk(base):
                for f in files:
                    f_lower = f.lower()
                    if name_lower in f_lower and (
                        f_lower.endswith(".exe") or f_lower.endswith(".lnk")
                    ):
                        return os.path.join(root, f)
        except PermissionError:
            continue
    return None


def _launch_app(cmd: str) -> str:
    """Launch an application process synchronously.

    Intended to be called via ``asyncio.to_thread`` so it never blocks the
    event loop.
    """
    os_name = platform.system()
    if os_name == "Windows":
        # ``start`` is a shell built-in that opens apps by name or association.
        subprocess.Popen(["start", "", cmd], shell=True)
    elif os_name == "Darwin":
        subprocess.Popen(["open", "-a", cmd])
    else:
        subprocess.Popen([cmd])
    return f"Launched: {cmd}"


class AppLauncherTool(BaseTool):
    """Launch applications on the user's computer.

    Resolves app names via: whitelist → PATH lookup → Windows install search.
    """

    name = "app_launcher"
    description = (
        "Launch an application on the user's computer. "
        "Pass the app name (e.g. 'notepad', 'edge', 'calc', 'firefox'). "
        "The tool auto-resolves the executable path on the system. "
        "For websites, use browser_control instead."
    )
    parameters = {
        "type": "object",
        "properties": {
            "app": {
                "type": "string",
                "description": (
                    "App name to launch, e.g. 'notepad', 'edge', 'calc'. "
                    "Can be a whitelisted name or any executable on the system."
                ),
            },
        },
        "required": ["app"],
    }

    async def execute(self, app: str, **_kwargs: Any) -> ToolResult:
        """Resolve and launch the requested application.

        Resolution order:
        1. Check whitelist mapping for known friendly names
        2. Search PATH for the executable
        3. (Windows) Search common install locations
        """
        logger.info("AppLauncherTool executing — app=%s", app)
        app_key = app.lower().strip()

        try:
            # Safety guard — only whitelisted apps are allowed.
            safety = SafetyGuard.check_app_launch(app)
            if not safety.allowed:
                logger.warning(
                    "AppLauncherTool blocked — app=%s reason=%s", app, safety.reason
                )
                return ToolResult(success=False, error=safety.reason)

            # Step 1: Check whitelist mapping
            cmd = _APP_COMMANDS.get(app_key)

            # Step 2: Try to find on PATH
            if cmd:
                resolved = _find_executable(cmd)
                if not resolved and platform.system() == "Windows":
                    resolved = _find_windows_app(cmd)
                if resolved:
                    cmd = resolved
                # If not found on PATH, still try the mapped name (start command may resolve it)
            else:
                # Not in whitelist mapping but passed safety — try to find directly
                resolved = _find_executable(app_key)
                if not resolved and platform.system() == "Windows":
                    resolved = _find_windows_app(app_key)
                if resolved:
                    cmd = resolved
                else:
                    cmd = app_key  # Last resort: let OS try to resolve

            result_msg = await asyncio.to_thread(_launch_app, cmd)

            logger.info("AppLauncherTool launched — app=%s cmd=%s", app, cmd)
            return ToolResult(
                success=True,
                data=result_msg,
                metadata={"app": app, "cmd": cmd, "os": platform.system()},
            )

        except Exception as exc:
            logger.error("AppLauncherTool failed — app=%s: %s", app, exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))
