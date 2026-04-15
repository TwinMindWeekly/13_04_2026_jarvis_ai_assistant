"""Unit tests for SafetyGuard, SafetyLevel, and SafetyResult."""

import pytest

from app.tools.safety import SafetyGuard, SafetyLevel, SafetyResult


# ---------------------------------------------------------------------------
# SafetyGuard.check_command
# ---------------------------------------------------------------------------


def test_check_command_safe():
    """A regular command returns allowed=True."""
    result = SafetyGuard.check_command("echo hello")
    assert result.allowed is True
    assert result.level != SafetyLevel.BLOCK


def test_check_command_blocks_rm_rf():
    """'rm -rf /' is BLOCKED outright."""
    result = SafetyGuard.check_command("rm -rf /")
    assert result.allowed is False
    assert result.level == SafetyLevel.BLOCK


def test_check_command_blocks_format():
    """'format C:' is BLOCKED outright."""
    result = SafetyGuard.check_command("format C:")
    assert result.allowed is False
    assert result.level == SafetyLevel.BLOCK


def test_check_command_blocks_shutdown():
    """'shutdown' is BLOCKED outright."""
    result = SafetyGuard.check_command("shutdown -s")
    assert result.allowed is False
    assert result.level == SafetyLevel.BLOCK


def test_check_command_case_insensitive():
    """Blocked keywords matched case-insensitively — 'RM -RF /' still BLOCKED."""
    result = SafetyGuard.check_command("RM -RF /")
    assert result.allowed is False
    assert result.level == SafetyLevel.BLOCK


def test_check_command_returns_safety_result_type():
    """check_command always returns a SafetyResult instance."""
    result = SafetyGuard.check_command("ls -la")
    assert isinstance(result, SafetyResult)


def test_check_command_reason_non_empty():
    """SafetyResult.reason is always a non-empty string."""
    result = SafetyGuard.check_command("dir")
    assert isinstance(result.reason, str)
    assert len(result.reason) > 0


# ---------------------------------------------------------------------------
# SafetyGuard.check_file_path
# ---------------------------------------------------------------------------


def test_check_file_path_user_dir_read():
    """A path inside the user home directory returns allowed=True, level=AUTO for reads."""
    result = SafetyGuard.check_file_path("C:\\Users\\user\\Documents\\notes.txt", write=False)
    assert result.allowed is True
    assert result.level == SafetyLevel.AUTO


def test_check_file_path_user_dir_write():
    """A path inside the user home directory returns allowed=True for writes (level CONFIRM)."""
    result = SafetyGuard.check_file_path("C:\\Users\\user\\Documents\\notes.txt", write=True)
    assert result.allowed is True
    assert result.level == SafetyLevel.CONFIRM


def test_check_file_path_blocks_windows():
    """'C:\\Windows\\System32\\hosts' is BLOCKED."""
    result = SafetyGuard.check_file_path("C:\\Windows\\System32\\hosts")
    assert result.allowed is False
    assert result.level == SafetyLevel.BLOCK


def test_check_file_path_blocks_program_files():
    """'C:\\Program Files\\test' is BLOCKED."""
    result = SafetyGuard.check_file_path("C:\\Program Files\\test")
    assert result.allowed is False
    assert result.level == SafetyLevel.BLOCK


def test_check_file_path_write_requires_confirm():
    """A write to a safe path returns requires_confirmation=True."""
    result = SafetyGuard.check_file_path("C:\\Users\\user\\Desktop\\test.txt", write=True)
    assert result.requires_confirmation is True


def test_check_file_path_read_no_confirm_required():
    """A read of a safe path does NOT require confirmation."""
    result = SafetyGuard.check_file_path("C:\\Users\\user\\Desktop\\test.txt", write=False)
    assert result.requires_confirmation is False


def test_check_file_path_default_is_read():
    """write defaults to False — calling without write=True behaves as a read check."""
    result = SafetyGuard.check_file_path("C:\\Users\\user\\file.txt")
    assert result.level == SafetyLevel.AUTO


# ---------------------------------------------------------------------------
# SafetyGuard.check_app_launch
# ---------------------------------------------------------------------------


def test_check_app_launch_notepad():
    """'notepad' is whitelisted — allowed=True."""
    result = SafetyGuard.check_app_launch("notepad")
    assert result.allowed is True
    assert result.level == SafetyLevel.NOTIFY


def test_check_app_launch_chrome():
    """'chrome' is whitelisted — allowed=True."""
    result = SafetyGuard.check_app_launch("chrome")
    assert result.allowed is True


def test_check_app_launch_unknown():
    """An unlisted app like 'malware.exe' is BLOCKED."""
    result = SafetyGuard.check_app_launch("malware.exe")
    assert result.allowed is False
    assert result.level == SafetyLevel.BLOCK


def test_check_app_launch_case_insensitive():
    """'NOTEPAD' (upper-case) is still allowed — check is case-insensitive."""
    result = SafetyGuard.check_app_launch("NOTEPAD")
    assert result.allowed is True


def test_check_app_launch_returns_safety_result_type():
    """check_app_launch always returns a SafetyResult instance."""
    result = SafetyGuard.check_app_launch("notepad")
    assert isinstance(result, SafetyResult)
