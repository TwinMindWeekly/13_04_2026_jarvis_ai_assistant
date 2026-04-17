"""Safety guard for evaluating tool actions before execution."""

from dataclasses import dataclass
from enum import IntEnum


class SafetyLevel(IntEnum):
    AUTO = 1     # Auto-approve: read file, search, screenshot
    NOTIFY = 2   # Inform user but proceed: open app, navigate web
    CONFIRM = 3  # Require explicit confirmation: write file, click sensitive UI
    BLOCK = 4    # Reject outright: delete system files, format, shutdown


@dataclass
class SafetyResult:
    """Outcome of a safety check."""

    allowed: bool
    level: SafetyLevel
    reason: str
    requires_confirmation: bool = False


class SafetyGuard:
    """Evaluate whether a tool action is safe to execute.

    All methods are class methods — no instance state is required.
    """

    BLOCKED_KEYWORDS: list[str] = [
        "rm -rf /",
        "rm -rf /*",
        "format c:",
        "del /s /q c:\\",
        "shutdown",
        "reboot",
        "rmdir /s",
        "diskpart",
        "regedit /s",
        "system32",
        "mkfs",
        "dd if=",
        ":(){ :|:& };:",
        "reg delete",
        "taskkill /f /im",
        "net user",
        "net localgroup",
        "bcdedit",
        "sfc /scannow",
    ]

    BLOCKED_FILE_PATHS: list[str] = [
        "C:\\Windows",
        "C:\\Program Files",
        "/etc",
        "/usr/bin",
        "/System",
        "/Library",
        "C:\\Users\\Default",
    ]

    APP_WHITELIST: list[str] = [
        "notepad",
        "calc",
        "calculator",
        "chrome",
        "msedge",
        "edge",
        "explorer",
        "code",
        "vscode",
        "firefox",
        "cmd",
        "powershell",
    ]

    @classmethod
    def check_command(cls, command: str) -> SafetyResult:
        """Check whether a shell command is safe to run.

        Args:
            command: The raw shell command string.

        Returns:
            SafetyResult indicating whether execution is allowed.
        """
        cmd_lower = command.lower().strip()
        for blocked in cls.BLOCKED_KEYWORDS:
            if blocked in cmd_lower:
                return SafetyResult(
                    allowed=False,
                    level=SafetyLevel.BLOCK,
                    reason=f"Command contains blocked keyword: {blocked}",
                )
        return SafetyResult(
            allowed=True,
            level=SafetyLevel.NOTIFY,
            reason="Command appears safe",
        )

    @classmethod
    def check_file_path(cls, path: str, write: bool = False) -> SafetyResult:
        """Check whether a file path is safe to access.

        Args:
            path:  Absolute file or directory path.
            write: True when the operation is a write; False for reads.

        Returns:
            SafetyResult with BLOCK for protected paths, CONFIRM for writes,
            AUTO for plain reads.
        """
        path_normalized = path.replace("/", "\\").lower()
        for blocked in cls.BLOCKED_FILE_PATHS:
            if blocked.lower() in path_normalized:
                return SafetyResult(
                    allowed=False,
                    level=SafetyLevel.BLOCK,
                    reason=f"Cannot access protected path: {blocked}",
                )
        if write:
            return SafetyResult(
                allowed=True,
                level=SafetyLevel.CONFIRM,
                reason="Write operation requires confirmation",
                requires_confirmation=True,
            )
        return SafetyResult(
            allowed=True,
            level=SafetyLevel.AUTO,
            reason="Read is safe",
        )

    @classmethod
    def check_app_launch(cls, app_name: str) -> SafetyResult:
        """Check whether an application is whitelisted for launch.

        Args:
            app_name: The name of the application to launch.

        Returns:
            SafetyResult with NOTIFY for whitelisted apps, BLOCK otherwise.
        """
        app_lower = app_name.lower().strip()
        if any(w in app_lower for w in cls.APP_WHITELIST):
            return SafetyResult(
                allowed=True,
                level=SafetyLevel.NOTIFY,
                reason=f"App '{app_name}' is whitelisted",
            )
        return SafetyResult(
            allowed=False,
            level=SafetyLevel.BLOCK,
            reason=f"App '{app_name}' is not in the whitelist",
        )
