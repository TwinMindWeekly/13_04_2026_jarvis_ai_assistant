"""Office automation tool — drive Word, Excel, PowerPoint via COM (Windows).

Uses pywin32's COM client to automate the installed Office suite. Compared
with UI automation (pyautogui clicks), COM is deterministic, fast, and
never falls out of sync with window focus.

Each Office app keeps a singleton COM handle so multiple calls reuse the
same running instance (e.g. create doc → paste image → save are three
separate tool calls but share one Word process).

Windows-only. Fails clean with a descriptive error if Office or pywin32
is not available.
"""

import asyncio
import logging
import os
import platform
import threading
from datetime import datetime
from typing import Any

from app.tools.base import BaseTool, ToolResult


def _default_save_path(ext: str, prefix: str = "JARVIS") -> str:
    """Build `<Desktop>/<prefix>-<timestamp>.<ext>` for the current user.

    Desktop resolution handles the common Windows OneDrive redirect —
    on managed Windows installs `%USERPROFILE%\\Desktop` often doesn't
    exist and the real Desktop lives under `%OneDrive%\\Desktop` or
    `%OneDriveCommercial%\\Desktop`.
    Falls back to the OS temp dir if none of the candidates are real.
    """
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{prefix}-{stamp}.{ext.lstrip('.')}"

    candidates: list[str] = []
    for env_var in ("OneDriveCommercial", "OneDrive"):
        base = os.environ.get(env_var)
        if base:
            candidates.append(os.path.join(base, "Desktop"))
    candidates.append(os.path.join(os.path.expanduser("~"), "Desktop"))

    for c in candidates:
        if os.path.isdir(c):
            return os.path.join(c, filename)

    import tempfile
    return os.path.join(tempfile.gettempdir(), filename)

logger = logging.getLogger(__name__)


# --- COM singletons ---------------------------------------------------------
# COM needs CoInitialize on each thread that touches it. We run every action
# on the same worker thread so we only init once.

_com_lock = threading.Lock()
_app_cache: dict[str, Any] = {}


def _ensure_com_initialized() -> None:
    """Call CoInitialize on the current thread if not already done."""
    import pythoncom  # noqa: PLC0415
    try:
        pythoncom.CoInitialize()
    except Exception:
        # Already initialized on this thread — ignore.
        pass


def _get_app(prog_id: str, visible: bool = True) -> Any:
    """Return (creating if needed) the singleton COM handle for prog_id.

    prog_id examples: "Word.Application", "Excel.Application".
    """
    _ensure_com_initialized()
    with _com_lock:
        app = _app_cache.get(prog_id)
        if app is not None:
            # Poke the handle — raises if the underlying process is gone.
            try:
                _ = app.Name
                return app
            except Exception:
                logger.info("Stale COM handle for %s — recreating", prog_id)
                _app_cache.pop(prog_id, None)

        import win32com.client  # noqa: PLC0415
        app = win32com.client.Dispatch(prog_id)
        app.Visible = visible
        _app_cache[prog_id] = app
        return app


# --- Action implementations -------------------------------------------------

def _word_app() -> Any:
    return _get_app("Word.Application", visible=True)


def _excel_app() -> Any:
    return _get_app("Excel.Application", visible=True)


def _powerpoint_app() -> Any:
    return _get_app("PowerPoint.Application", visible=True)


def _word_new_doc() -> str:
    """Create a new blank Word document and return a human-readable status."""
    app = _word_app()
    doc = app.Documents.Add()
    return f"Created new Word document: {doc.Name}"


def _word_open(path: str) -> str:
    app = _word_app()
    doc = app.Documents.Open(os.path.abspath(path))
    return f"Opened Word document: {doc.Name}"


def _word_insert_text(text: str) -> str:
    app = _word_app()
    if app.Documents.Count == 0:
        app.Documents.Add()
    app.Selection.TypeText(text)
    return f"Inserted {len(text)} characters at cursor."


def _word_paste() -> str:
    """Paste whatever is on the clipboard at the current cursor."""
    app = _word_app()
    if app.Documents.Count == 0:
        app.Documents.Add()
    app.Selection.Paste()
    return "Pasted clipboard contents into active document."


def _word_save_as(path: str | None = None) -> str:
    app = _word_app()
    if app.Documents.Count == 0:
        raise RuntimeError("No active Word document to save.")
    abs_path = os.path.abspath(path) if path else _default_save_path("docx")
    os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
    # FileFormat 16 = wdFormatDocumentDefault (.docx)
    app.ActiveDocument.SaveAs2(abs_path, FileFormat=16)
    return f"Saved Word document to: {abs_path}"


def _excel_new_workbook() -> str:
    app = _excel_app()
    wb = app.Workbooks.Add()
    return f"Created new Excel workbook: {wb.Name}"


def _excel_open(path: str) -> str:
    app = _excel_app()
    wb = app.Workbooks.Open(os.path.abspath(path))
    return f"Opened Excel workbook: {wb.Name}"


def _excel_write_cell(cell: str, value: str) -> str:
    app = _excel_app()
    if app.Workbooks.Count == 0:
        app.Workbooks.Add()
    ws = app.ActiveSheet
    ws.Range(cell).Value = value
    return f"Wrote {value!r} to {cell}."


def _excel_save_as(path: str | None = None) -> str:
    app = _excel_app()
    if app.Workbooks.Count == 0:
        raise RuntimeError("No active Excel workbook to save.")
    abs_path = os.path.abspath(path) if path else _default_save_path("xlsx")
    os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
    # FileFormat 51 = xlOpenXMLWorkbook (.xlsx)
    app.ActiveWorkbook.SaveAs(abs_path, FileFormat=51)
    return f"Saved Excel workbook to: {abs_path}"


def _powerpoint_new() -> str:
    app = _powerpoint_app()
    pres = app.Presentations.Add()
    # Ensure at least one slide so the user isn't looking at a blank window.
    if pres.Slides.Count == 0:
        pres.Slides.Add(1, 1)  # Layout 1 = ppLayoutTitle
    return f"Created new PowerPoint presentation: {pres.Name}"


def _powerpoint_save_as(path: str | None = None) -> str:
    app = _powerpoint_app()
    if app.Presentations.Count == 0:
        raise RuntimeError("No active PowerPoint presentation to save.")
    abs_path = os.path.abspath(path) if path else _default_save_path("pptx")
    os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
    # FileFormat 24 = ppSaveAsDefault (.pptx in modern PowerPoint)
    app.ActivePresentation.SaveAs(abs_path, 24)
    return f"Saved PowerPoint presentation to: {abs_path}"


# Map action → (handler, required_kwargs, optional_kwargs).
# save_as actions treat `path` as optional — when omitted, the handler writes
# to `<Desktop>/JARVIS-<timestamp>.<ext>` so the agent never has to resolve
# the Desktop path itself via code_runner/shell_exec.
_ACTIONS: dict[str, tuple[Any, list[str], list[str]]] = {
    "word_new":         (_word_new_doc,       [], []),
    "word_open":        (_word_open,          ["path"], []),
    "word_insert_text": (_word_insert_text,   ["text"], []),
    "word_paste":       (_word_paste,         [], []),
    "word_save_as":     (_word_save_as,       [], ["path"]),
    "excel_new":        (_excel_new_workbook, [], []),
    "excel_open":       (_excel_open,         ["path"], []),
    "excel_write_cell": (_excel_write_cell,   ["cell", "value"], []),
    "excel_save_as":    (_excel_save_as,      [], ["path"]),
    "powerpoint_new":   (_powerpoint_new,     [], []),
    "powerpoint_save_as": (_powerpoint_save_as, [], ["path"]),
}


class OfficeAutomationTool(BaseTool):
    """High-level Word / Excel / PowerPoint automation via COM."""

    name = "office_automation"
    description = (
        "Automate Microsoft Office apps (Word, Excel, PowerPoint) via COM. "
        "Deterministic alternative to clicking through the UI — prefer this "
        "over desktop_control whenever the action can be expressed as a COM call. "
        "Actions: "
        "word_new, word_open(path), word_insert_text(text), word_paste, word_save_as(path?); "
        "excel_new, excel_open(path), excel_write_cell(cell, value), excel_save_as(path?); "
        "powerpoint_new, powerpoint_save_as(path?). "
        "For *_save_as, `path` is OPTIONAL — omit it and the file is written to "
        "the user's Desktop as 'JARVIS-<timestamp>.<ext>'. Do NOT call "
        "code_runner/shell_exec to build a save path. "
        "Windows + Microsoft Office required."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": list(_ACTIONS.keys()),
                "description": "Which Office automation action to run.",
            },
            "path": {
                "type": "string",
                "description": "File path — required for open/save_as actions.",
            },
            "text": {
                "type": "string",
                "description": "Text to type — required for word_insert_text.",
            },
            "cell": {
                "type": "string",
                "description": "Excel cell reference like 'A1' or 'B3:C5'.",
            },
            "value": {
                "type": "string",
                "description": "Value to write into the Excel cell.",
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "").lower()

        if platform.system() != "Windows":
            return ToolResult(success=False, error="office_automation is Windows-only.")

        if action not in _ACTIONS:
            return ToolResult(
                success=False,
                error=f"Unknown action {action!r}. Valid: {', '.join(_ACTIONS.keys())}",
            )

        handler, required, optional = _ACTIONS[action]
        missing = [k for k in required if not kwargs.get(k)]
        if missing:
            return ToolResult(
                success=False,
                error=f"Action {action!r} requires: {', '.join(missing)}.",
            )

        call_kwargs = {k: kwargs[k] for k in required}
        for k in optional:
            if kwargs.get(k) is not None and kwargs.get(k) != "":
                call_kwargs[k] = kwargs[k]

        logger.info("OfficeAutomationTool — action=%s args=%s", action, call_kwargs)

        try:
            msg = await asyncio.to_thread(_invoke, handler, call_kwargs)
        except Exception as exc:
            logger.error("OfficeAutomationTool %s failed: %s", action, exc, exc_info=True)
            return ToolResult(
                success=False,
                error=f"{action} failed: {exc}. "
                      f"Is Microsoft Office installed and licensed?",
            )

        return ToolResult(
            success=True,
            data=msg,
            metadata={"action": action, **call_kwargs},
        )


def _invoke(handler: Any, kwargs: dict[str, Any]) -> str:
    """Run the handler on a thread with COM initialized."""
    _ensure_com_initialized()
    return handler(**kwargs)
