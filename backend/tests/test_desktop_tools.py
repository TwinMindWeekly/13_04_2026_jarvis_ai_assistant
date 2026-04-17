"""Unit tests for DesktopControlTool, FileManagerTool, and AppLauncherTool.

External dependencies (pyautogui, subprocess) are mocked so these tests run
in any CI environment without a display or real applications installed.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools.base import ToolResult
from app.tools.desktop_control import DesktopControlTool
from app.tools.file_manager import FileManagerTool
from app.tools.app_launcher import AppLauncherTool


# ===========================================================================
# Helpers — pyautogui mock injection
# ===========================================================================


def _inject_pyautogui_mock() -> MagicMock:
    """Create and inject a fake pyautogui module into sys.modules.

    Returns the mock module so individual tests can assert on its callables.
    The fake PIL Image returned by screenshot() has .size, .thumbnail, and
    .save attributes that match the real API used by _capture_screenshot_sync.
    """
    mock = types.ModuleType("pyautogui")
    mock.FAILSAFE = True  # type: ignore[attr-defined]
    mock.click = MagicMock()  # type: ignore[attr-defined]
    mock.doubleClick = MagicMock()  # type: ignore[attr-defined]
    mock.rightClick = MagicMock()  # type: ignore[attr-defined]
    mock.write = MagicMock()  # type: ignore[attr-defined]
    mock.hotkey = MagicMock()  # type: ignore[attr-defined]
    mock.scroll = MagicMock()  # type: ignore[attr-defined]
    mock.moveTo = MagicMock()  # type: ignore[attr-defined]

    # screenshot returns a PIL Image-like object
    fake_img = MagicMock()
    fake_img.size = (1920, 1080)
    fake_img.thumbnail = MagicMock()
    fake_img.save = MagicMock()
    mock.screenshot = MagicMock(return_value=fake_img)  # type: ignore[attr-defined]

    sys.modules["pyautogui"] = mock  # type: ignore[assignment]
    return mock  # type: ignore[return-value]


def _remove_pyautogui_mock() -> None:
    sys.modules.pop("pyautogui", None)


# ===========================================================================
# DesktopControlTool tests
# ===========================================================================


@pytest.fixture(autouse=False)
def pyautogui_mock():
    """Inject the pyautogui mock before each desktop test, remove after."""
    mock = _inject_pyautogui_mock()
    yield mock
    _remove_pyautogui_mock()


async def test_desktop_click(pyautogui_mock: MagicMock) -> None:
    """action='click' succeeds and delegates to pyautogui.click(x, y)."""
    tool = DesktopControlTool()
    result = await tool.execute(action="click", x=100, y=200)

    assert result.success is True
    pyautogui_mock.click.assert_called_once_with(100, 200)


async def test_desktop_type(pyautogui_mock: MagicMock) -> None:
    """action='type' succeeds and delegates to pyautogui.write."""
    tool = DesktopControlTool()
    result = await tool.execute(action="type", text="hello")

    assert result.success is True
    pyautogui_mock.write.assert_called_once()
    args, _ = pyautogui_mock.write.call_args
    assert args[0] == "hello"


async def test_desktop_hotkey(pyautogui_mock: MagicMock) -> None:
    """action='hotkey' with keys='ctrl+c' calls pyautogui.hotkey('ctrl', 'c')."""
    tool = DesktopControlTool()
    result = await tool.execute(action="hotkey", keys="ctrl+c")

    assert result.success is True
    pyautogui_mock.hotkey.assert_called_once_with("ctrl", "c")


async def test_desktop_double_click(pyautogui_mock: MagicMock) -> None:
    """action='double_click' succeeds and delegates to pyautogui.doubleClick."""
    tool = DesktopControlTool()
    result = await tool.execute(action="double_click", x=50, y=75)

    assert result.success is True
    pyautogui_mock.doubleClick.assert_called_once_with(50, 75)


async def test_desktop_scroll(pyautogui_mock: MagicMock) -> None:
    """action='scroll' succeeds and delegates to pyautogui.scroll."""
    tool = DesktopControlTool()
    result = await tool.execute(action="scroll", amount=5)

    assert result.success is True
    pyautogui_mock.scroll.assert_called_once_with(5)


async def test_desktop_move(pyautogui_mock: MagicMock) -> None:
    """action='move' succeeds and delegates to pyautogui.moveTo."""
    tool = DesktopControlTool()
    result = await tool.execute(action="move", x=300, y=400)

    assert result.success is True
    pyautogui_mock.moveTo.assert_called_once()


async def test_desktop_unknown_action(pyautogui_mock: MagicMock) -> None:
    """An unrecognised action returns success=False."""
    tool = DesktopControlTool()
    result = await tool.execute(action="invalid_action")

    assert result.success is False
    assert result.error is not None


async def test_desktop_screenshot_in_metadata(pyautogui_mock: MagicMock) -> None:
    """Every successful desktop action includes a 'screenshot' key in metadata."""
    tool = DesktopControlTool()
    result = await tool.execute(action="click", x=10, y=20)

    assert result.success is True
    assert "screenshot" in result.metadata


async def test_desktop_returns_tool_result(pyautogui_mock: MagicMock) -> None:
    """execute() always returns a ToolResult instance."""
    tool = DesktopControlTool()
    result = await tool.execute(action="click", x=0, y=0)
    assert isinstance(result, ToolResult)


# ===========================================================================
# FileManagerTool tests
# ===========================================================================


async def test_file_read(tmp_path: Path) -> None:
    """Reading an existing file returns its content."""
    target = tmp_path / "hello.txt"
    target.write_text("Hello, JARVIS!", encoding="utf-8")

    tool = FileManagerTool()
    result = await tool.execute(action="read", path=str(target))

    assert result.success is True
    assert result.data == "Hello, JARVIS!"


async def test_file_write(tmp_path: Path) -> None:
    """Writing content creates the file with the exact content."""
    target = tmp_path / "output.txt"

    tool = FileManagerTool()
    result = await tool.execute(action="write", path=str(target), content="Written by test")

    assert result.success is True
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "Written by test"


async def test_file_list(tmp_path: Path) -> None:
    """Listing a directory returns its entries."""
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")

    tool = FileManagerTool()
    result = await tool.execute(action="list", path=str(tmp_path))

    assert result.success is True
    assert "a.txt" in result.data
    assert "b.txt" in result.data


async def test_file_exists_true(tmp_path: Path) -> None:
    """exists action returns 'True' when the path exists."""
    target = tmp_path / "exists.txt"
    target.write_text("yes")

    tool = FileManagerTool()
    result = await tool.execute(action="exists", path=str(target))

    assert result.success is True
    assert result.data == "True"


async def test_file_exists_false(tmp_path: Path) -> None:
    """exists action returns 'False' when the path does not exist."""
    missing = tmp_path / "missing.txt"

    tool = FileManagerTool()
    result = await tool.execute(action="exists", path=str(missing))

    assert result.success is True
    assert result.data == "False"


async def test_file_blocked_windows_path() -> None:
    """Reading a protected Windows path is blocked — success=False."""
    tool = FileManagerTool()
    result = await tool.execute(action="read", path="C:\\Windows\\test.txt")

    assert result.success is False
    assert result.error is not None


async def test_file_blocked_program_files() -> None:
    """Reading C:\\Program Files path is blocked — success=False."""
    tool = FileManagerTool()
    result = await tool.execute(action="read", path="C:\\Program Files\\SomeApp\\config.ini")

    assert result.success is False
    assert result.error is not None


async def test_file_not_found(tmp_path: Path) -> None:
    """Reading a non-existent file returns success=False with an error message."""
    missing = tmp_path / "does_not_exist.txt"

    tool = FileManagerTool()
    result = await tool.execute(action="read", path=str(missing))

    assert result.success is False
    assert result.error is not None


async def test_file_write_creates_parent_dirs(tmp_path: Path) -> None:
    """Writing to a path with non-existent parents creates the directories."""
    target = tmp_path / "deep" / "nested" / "file.txt"

    tool = FileManagerTool()
    result = await tool.execute(action="write", path=str(target), content="nested content")

    assert result.success is True
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "nested content"


async def test_file_metadata_contains_path(tmp_path: Path) -> None:
    """Successful operations include 'path' and 'action' in metadata."""
    target = tmp_path / "meta.txt"
    target.write_text("metadata test")

    tool = FileManagerTool()
    result = await tool.execute(action="read", path=str(target))

    assert result.success is True
    assert result.metadata.get("path") == str(target)
    assert result.metadata.get("action") == "read"


# ===========================================================================
# AppLauncherTool tests — cascade resolver + blocklist safety
# ===========================================================================


def _patch_launcher(resolved: str | None = "C:\\fake\\app.exe"):
    """Patch the resolver to return `resolved` and Popen to a mock.

    Returns a context manager yielding the Popen mock. Pass resolved=None to
    simulate an app that could not be found.
    """
    class _Ctx:
        def __enter__(self_):
            self_._rp = patch(
                "app.tools.app_launcher._resolve_cascade", return_value=resolved,
            )
            self_._pp = patch("app.tools.app_launcher.subprocess.Popen")
            self_._rp.start()
            self_.popen = self_._pp.start()
            return self_.popen

        def __exit__(self_, *a):
            self_._pp.stop()
            self_._rp.stop()

    return _Ctx()


async def test_launch_notepad() -> None:
    """Launching 'notepad' succeeds when the resolver finds an executable."""
    with _patch_launcher("C:\\Windows\\System32\\notepad.exe") as popen:
        tool = AppLauncherTool()
        result = await tool.execute(app="notepad")

    assert result.success is True
    popen.assert_called_once()


async def test_launch_unknown_app_blocked() -> None:
    """A dangerous string containing shell metacharacters is rejected."""
    with _patch_launcher() as popen:
        tool = AppLauncherTool()
        result = await tool.execute(app="notepad & rm -rf /")

    assert result.success is False
    assert result.error is not None
    popen.assert_not_called()


async def test_launch_app_not_found() -> None:
    """When the resolver cannot locate the app, launch fails cleanly."""
    with _patch_launcher(resolved=None) as popen:
        tool = AppLauncherTool()
        result = await tool.execute(app="definitely-not-installed")

    assert result.success is False
    assert "locate" in (result.error or "").lower()
    popen.assert_not_called()


async def test_launch_calc_alias() -> None:
    """'calculator' aliases to 'calc' and Popen is invoked."""
    with _patch_launcher("C:\\Windows\\System32\\calc.exe") as popen:
        tool = AppLauncherTool()
        result = await tool.execute(app="calculator")

    assert result.success is True
    assert result.metadata.get("resolved", "").lower().endswith("calc.exe")
    popen.assert_called_once()


async def test_launch_chrome() -> None:
    """Launching 'chrome' succeeds via the cascade resolver."""
    with _patch_launcher("C:\\Program Files\\Google\\Chrome\\chrome.exe") as popen:
        tool = AppLauncherTool()
        result = await tool.execute(app="chrome")

    assert result.success is True
    popen.assert_called_once()


async def test_launch_metadata_contains_app_and_resolved() -> None:
    """Successful launches include 'app' and 'resolved' metadata keys."""
    with _patch_launcher("C:\\fake\\notepad.exe"):
        tool = AppLauncherTool()
        result = await tool.execute(app="notepad")

    assert result.success is True
    assert result.metadata.get("app") == "notepad"
    assert "resolved" in result.metadata


async def test_launch_returns_tool_result() -> None:
    """execute() always returns a ToolResult instance."""
    with _patch_launcher("C:\\fake\\notepad.exe"):
        tool = AppLauncherTool()
        result = await tool.execute(app="notepad")
    assert isinstance(result, ToolResult)


async def test_launch_case_insensitive_alias() -> None:
    """'NOTEPAD' (upper-case) resolves just like 'notepad'."""
    with _patch_launcher("C:\\fake\\notepad.exe") as popen:
        tool = AppLauncherTool()
        result = await tool.execute(app="NOTEPAD")

    assert result.success is True
    popen.assert_called_once()
