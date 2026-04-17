---
name: windows-office-automation
description: "Use this skill when the user wants to open, edit, or automate Microsoft Office applications on Windows — especially Word, Excel, or PowerPoint. Triggers include any mention of 'word', 'winword', 'excel', 'powerpoint', 'pptx', 'spreadsheet', combined with actions like 'open', 'create', 'paste', 'screenshot into', 'save as'. Also use when the user wants to take a screenshot and paste it into another app, or script a repeatable desktop workflow that Office already exposes via COM. Do NOT use this skill for generating .docx/.xlsx files without opening Office — for that use the dedicated docx / xlsx skills."
---

# Windows Office automation

## When to use `office_automation` vs `desktop_control`

Always prefer `office_automation` when the operation can be expressed as a
COM call. It is deterministic, fast, and never loses focus. Only fall back
to `desktop_control` (mouse/keyboard simulation) for actions COM cannot
reach (e.g. interacting with a dialog button that has no COM equivalent).

## Tool matrix

| Goal | Tool call |
|------|-----------|
| Launch Word/Excel/etc. | `app_launcher(app="word")` (or `excel`, `powerpoint`, …) |
| Create blank Word doc | `office_automation(action="word_new")` |
| Insert text at cursor | `office_automation(action="word_insert_text", text="…")` |
| Paste clipboard into doc | `office_automation(action="word_paste")` |
| Save Word doc (user gave a path) | `office_automation(action="word_save_as", path="C:\\…\\out.docx")` |
| Save Word doc (no path given) | `office_automation(action="word_save_as")` — omit path → Desktop/JARVIS-<timestamp>.docx |
| New Excel workbook | `office_automation(action="excel_new")` |
| Write a cell | `office_automation(action="excel_write_cell", cell="A1", value="…")` |
| Save Excel (no path) | `office_automation(action="excel_save_as")` — omit path → Desktop default |
| New PowerPoint | `office_automation(action="powerpoint_new")` |
| Save PowerPoint (no path) | `office_automation(action="powerpoint_save_as")` — omit path → Desktop default |
| Take screenshot onto clipboard | `screenshot(to_clipboard=true)` |
| Put existing image on clipboard | `clipboard(action="write_image", content="<base64>")` |
| Read image from clipboard | `clipboard(action="read_image")` |

## Canonical recipes

### 1. "Open Word, create a new file, take a screenshot, paste it, save"

Four tool calls, no clicks:

1. `office_automation(action="word_new")`
2. `screenshot(to_clipboard=true)`
3. `office_automation(action="word_paste")`
4. `office_automation(action="word_save_as")` — path omitted → Desktop/JARVIS-<timestamp>.docx

Do NOT use `app_launcher("word")` first — `office_automation` starts Word
automatically via COM if it's not running.

### 2. "Put a quick note into a spreadsheet"

1. `office_automation(action="excel_new")`
2. `office_automation(action="excel_write_cell", cell="A1", value="Note title")`
3. `office_automation(action="excel_write_cell", cell="A2", value="…body…")`
4. `office_automation(action="excel_save_as")` — path omitted → Desktop default

### 3. "Screenshot and copy to clipboard for me"

Just one call:

1. `screenshot(to_clipboard=true)` — the user can now Ctrl+V anywhere.

## Anti-patterns (don't do these)

- **Don't** call `code_runner` or `shell_exec` to figure out where the
  Desktop is, to find `%USERPROFILE%`, or to build a save path. Just omit
  the `path` argument — `office_automation` defaults to the user's Desktop.
- **Don't** call `app_launcher("word")` before `office_automation(action="word_new")`.
  The COM automation starts Word itself.

## Pitfalls

- Paths **must** be absolute on Windows. Forward slashes are accepted by
  most COM APIs but use `\\` in examples for clarity.
- If Office is not installed or not licensed, the tool returns a descriptive
  error — do not retry, tell the user to install Office.
- The clipboard holds **one** item. `screenshot(to_clipboard=true)`
  overwrites whatever was there previously.
- COM apps opened this way are visible by default. That is intentional so
  the user can see the result.
