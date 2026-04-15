"""App launcher tool for opening whitelisted applications on the host OS."""

import asyncio
import logging
import platform
import subprocess
from typing import Any

from app.tools.base import BaseTool, ToolResult
from app.tools.safety import SafetyGuard

logger = logging.getLogger(__name__)

# Maps friendly user-facing names to the executable name used for each OS.
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


def _launch_app(cmd: str) -> str:
    """Launch an application process synchronously.

    Intended to be called via ``asyncio.to_thread`` so it never blocks the
    event loop.

    Args:
        cmd: Executable name or path.

    Returns:
        Human-readable confirmation message.

    Raises:
        OSError / subprocess.SubprocessError on launch failure.
    """
    os_name = platform.system()
    if os_name == "Windows":
        # ``start`` is a shell built-in that opens apps by name or association.
        subprocess.Popen(["start", "", cmd], shell=True)
    elif os_name == "Darwin":
        subprocess.Popen(["open", "-a", cmd])
    else:
        # Linux / other POSIX — assume the command is on PATH.
        subprocess.Popen([cmd])
    return f"Launched: {cmd}"


class AppLauncherTool(BaseTool):
    """Launch whitelisted applications on the user's computer.

    Only applications in the SafetyGuard whitelist may be started.  The tool
    resolves friendly names (e.g. "calculator", "vscode") to the correct
    executable and delegates the actual process creation to the OS shell so
    that file associations and PATH resolution work as expected.
    """

    name = "app_launcher"
    description = (
        "Launch an application on the user's computer. "
        "Available apps: notepad, calculator (calc), chrome, edge, firefox, "
        "vscode (code), explorer, cmd, powershell."
    )
    parameters = {
        "type": "object",
        "properties": {
            "app": {
                "type": "string",
                "description": (
                    "App name to launch, e.g. 'notepad', 'chrome', 'calc'. "
                    "Must be one of the whitelisted applications."
                ),
            },
        },
        "required": ["app"],
    }

    async def execute(self, app: str, **_kwargs: Any) -> ToolResult:  # type: ignore[override]
        """Check safety and launch the requested application.

        Args:
            app: Friendly application name (case-insensitive).

        Returns:
            ToolResult confirming the launch, or an error if the app is not
            whitelisted or cannot be started.
        """
        logger.info("AppLauncherTool executing — app=%s", app)

        try:
            # Safety guard — only whitelisted apps are allowed.
            safety = SafetyGuard.check_app_launch(app)
            if not safety.allowed:
                logger.warning(
                    "AppLauncherTool blocked — app=%s reason=%s", app, safety.reason
                )
                return ToolResult(success=False, error=safety.reason)

            cmd = _APP_COMMANDS.get(app.lower().strip())
            if not cmd:
                return ToolResult(
                    success=False,
                    error=(
                        f"App '{app}' is whitelisted but has no registered command. "
                        "Supported names: " + ", ".join(_APP_COMMANDS)
                    ),
                )

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
