r"""App launcher tool — opens applications or URLs on the host OS.

Resolution cascade (Windows):
  1. Friendly-name shortcut map (notepad, edge, word, excel, …)
  2. PATH lookup (`where` / `which`)
  3. Registry `App Paths` key
  4. Start Menu shortcuts under Programs folder
  5. `Get-StartApps` PowerShell → launch via `shell:AppsFolder\{AUMID}`

Whitelist was removed in favor of a BLOCKED-list (keeps shell-injection
guardrails but lets the agent launch any installed application).
"""

import asyncio
import logging
import os
import platform
import re
import subprocess
import webbrowser
from typing import Any

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Friendly names → canonical executable / AUMID fragment.
# Keys are matched case-insensitively against user input.
_APP_SHORTCUTS: dict[str, str] = {
    # Browsers
    "chrome": "chrome",
    "edge": "msedge",
    "msedge": "msedge",
    "firefox": "firefox",
    # Dev / system
    "notepad": "notepad",
    "calc": "calc",
    "calculator": "calc",
    "explorer": "explorer",
    "cmd": "cmd",
    "powershell": "powershell",
    "terminal": "wt",
    "code": "code",
    "vscode": "code",
    # Office (resolved via AUMID if .exe not on PATH)
    "word": "winword",
    "winword": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "ppt": "powerpnt",
    "outlook": "outlook",
    "onenote": "onenote",
    # Communication / misc
    "teams": "teams",
    "slack": "slack",
    "discord": "discord",
    "spotify": "spotify",
    "zoom": "zoom",
}

# Hard-blocked patterns — keeps shell-injection and destructive launches out
# even when the whitelist is gone. Matched case-insensitively as substrings.
_BLOCKED_PATTERNS: list[str] = [
    "&", "|", ";", "`",           # shell metacharacters
    "..\\", "../",                  # path traversal
    "format ", "shutdown", "diskpart", "mkfs", "reg delete", "bcdedit",
]


def _is_blocked(app: str) -> str | None:
    """Return reason if app string contains a blocked pattern, else None."""
    low = app.lower()
    for pat in _BLOCKED_PATTERNS:
        if pat in low:
            return f"App string contains blocked pattern: {pat!r}"
    return None


def _find_on_path(name: str) -> str | None:
    """Find executable on PATH via `where` (Win) or `which` (POSIX)."""
    cmd = ["where", name] if platform.system() == "Windows" else ["which", name]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def _find_in_registry(name: str) -> str | None:
    """Check Windows registry `App Paths` for an installed application.

    Looks at both HKLM and HKCU under
    Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\<name>.exe.
    """
    if platform.system() != "Windows":
        return None
    try:
        import winreg  # noqa: PLC0415
    except ImportError:
        return None

    key_name = name if name.lower().endswith(".exe") else f"{name}.exe"
    sub_key = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{key_name}"

    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, sub_key) as h:
                path, _ = winreg.QueryValueEx(h, "")
                if path and os.path.isfile(path):
                    return path
        except OSError:
            continue
    return None


def _find_start_menu_shortcut(name: str) -> str | None:
    """Walk Start Menu Programs folders for a matching .lnk or .exe."""
    if platform.system() != "Windows":
        return None
    name_low = name.lower()
    bases = [
        os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
    ]
    for base in bases:
        if not os.path.isdir(base):
            continue
        try:
            for root, _dirs, files in os.walk(base):
                for f in files:
                    low = f.lower()
                    if name_low in low and (low.endswith(".lnk") or low.endswith(".exe")):
                        return os.path.join(root, f)
        except PermissionError:
            continue
    return None


def _find_aumid(name: str) -> str | None:
    """Query `Get-StartApps` for an AppUserModelID matching `name`.

    Returns the AUMID (e.g. `Microsoft.Office.WINWORD.EXE.15`) that can be
    launched via `explorer shell:AppsFolder\\{AUMID}`.
    """
    if platform.system() != "Windows":
        return None
    name_low = name.lower()
    ps_cmd = (
        "Get-StartApps | "
        "ForEach-Object { \"$($_.Name)|$($_.AppID)\" }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=8,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None

    # Prefer exact-ish match on Name, fall back to AppID match.
    for line in result.stdout.splitlines():
        if "|" not in line:
            continue
        disp, aumid = line.split("|", 1)
        if name_low in disp.lower() or name_low in aumid.lower():
            return aumid.strip()
    return None


def _is_url(text: str) -> bool:
    """Return True when text looks like a URL."""
    return text.startswith(("http://", "https://", "www."))


def _open_url(url: str) -> str:
    """Open a URL in the user's default browser."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened in default browser: {url}"


def _launch_resolved(resolved: str) -> str:
    """Launch a resolved target — path, bare command, or shell:AppsFolder spec."""
    os_name = platform.system()
    if os_name == "Windows":
        if resolved.lower().startswith("shell:"):
            # AUMID launch via explorer.
            subprocess.Popen(["explorer", resolved], shell=False)
        else:
            # `start ""` handles both .exe paths and .lnk shortcuts.
            subprocess.Popen(["cmd", "/c", "start", "", resolved], shell=False)
    elif os_name == "Darwin":
        subprocess.Popen(["open", "-a", resolved])
    else:
        subprocess.Popen([resolved])
    return f"Launched: {resolved}"


class AppLauncherTool(BaseTool):
    """Launch any installed application or open a URL.

    Windows resolution cascade: shortcuts → PATH → registry App Paths →
    Start Menu → Get-StartApps AUMID. Safety is enforced by blocklist only —
    any installed app can be launched.
    """

    name = "app_launcher"
    description = (
        "Launch an application installed on the user's computer, or open a URL. "
        "Accepts friendly names (e.g. 'word', 'excel', 'chrome', 'spotify', "
        "'teams', 'notepad') OR an executable path, OR a URL. Tries multiple "
        "resolution strategies before giving up, so most installed apps work "
        "without special configuration."
    )
    parameters = {
        "type": "object",
        "properties": {
            "app": {
                "type": "string",
                "description": (
                    "App name or URL. Examples: 'word', 'excel', 'chrome', "
                    "'https://youtube.com', 'C:\\\\Path\\\\To\\\\App.exe'."
                ),
            },
        },
        "required": ["app"],
    }

    async def execute(self, app: str, **_kwargs: Any) -> ToolResult:
        """Resolve and launch `app` using the cascade above."""
        logger.info("AppLauncherTool executing — app=%r", app)
        raw = app.strip()

        if not raw:
            return ToolResult(success=False, error="App name cannot be empty.")

        # URL shortcut — no resolution needed.
        if _is_url(raw):
            try:
                msg = await asyncio.to_thread(_open_url, raw)
                return ToolResult(
                    success=True,
                    data=msg,
                    metadata={"type": "url", "url": raw},
                )
            except Exception as exc:
                logger.error("AppLauncherTool URL open failed: %s", exc)
                return ToolResult(success=False, error=str(exc))

        # Reject obviously dangerous strings (injection / destructive commands).
        blocked = _is_blocked(raw)
        if blocked:
            logger.warning("AppLauncherTool blocked — %s", blocked)
            return ToolResult(success=False, error=blocked)

        # Normalize: lowercase for shortcut lookup, but keep original for absolute paths.
        key = raw.lower()

        # Absolute path shortcut — launch directly if it exists.
        if os.path.isabs(raw) and os.path.exists(raw):
            try:
                msg = await asyncio.to_thread(_launch_resolved, raw)
                return ToolResult(success=True, data=msg, metadata={"resolved": raw})
            except Exception as exc:
                return ToolResult(success=False, error=str(exc))

        # Canonical name (from shortcut map) or fall back to user input.
        target = _APP_SHORTCUTS.get(key, re.sub(r"\.exe$", "", key, flags=re.I))

        try:
            resolved = await asyncio.to_thread(_resolve_cascade, target, raw)
        except Exception as exc:
            logger.error("AppLauncherTool resolve failed: %s", exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))

        if not resolved:
            return ToolResult(
                success=False,
                error=(
                    f"Could not locate '{app}'. Tried PATH, registry, Start Menu, "
                    f"and Get-StartApps. Is the application installed?"
                ),
            )

        try:
            msg = await asyncio.to_thread(_launch_resolved, resolved)
        except Exception as exc:
            logger.error("AppLauncherTool launch failed: %s", exc)
            return ToolResult(success=False, error=str(exc))

        logger.info("AppLauncherTool launched — %r -> %r", app, resolved)
        return ToolResult(
            success=True,
            data=msg,
            metadata={"app": app, "resolved": resolved, "os": platform.system()},
        )


def _resolve_cascade(canonical: str, original: str) -> str | None:
    """Run the full resolution cascade. Returns first non-None match.

    `canonical` is the shortcut-mapped name (e.g. `winword` for `word`);
    `original` is what the user typed, used for Start-Menu/AUMID fuzzy match.
    """
    for candidate in (canonical, original):
        if not candidate:
            continue

        found = _find_on_path(candidate)
        if found:
            return found

        found = _find_in_registry(candidate)
        if found:
            return found

        found = _find_start_menu_shortcut(candidate)
        if found:
            return found

        aumid = _find_aumid(candidate)
        if aumid:
            return f"shell:AppsFolder\\{aumid}"

    return None
