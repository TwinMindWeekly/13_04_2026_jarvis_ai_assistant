# JARVIS Tool Catalog

> Tham khao nhanh tat ca tools hien tai va de xuat tool moi.
> Cap nhat: 16/04/2026

---

## Tools hien tai (8 tools)

### 1. web_search — Tim kiem internet
| | |
|---|---|
| **File** | `backend/app/tools/web_search.py` |
| **Safety** | AUTO |
| **Engine** | DuckDuckGo (mien phi, khong can API key) |

**Parameters:**
- `query` (string) — tu khoa tim kiem
- `num_results` (int, default 5) — so ket qua

**Kha nang:** Tim kiem internet, tra ve title/snippet/url.
**Han che:** Khong loc theo ngay/ngon ngu/khu vuc. Toi da 5000 ky tu/ket qua.

---

### 2. web_browser — Doc noi dung trang web
| | |
|---|---|
| **File** | `backend/app/tools/web_browser.py` |
| **Safety** | AUTO (get_text) / NOTIFY (screenshot) |
| **Engine** | Playwright Chromium headless |

**Parameters:**
- `url` (string) — URL can doc
- `action` ("get_text" | "screenshot")

**Kha nang:** Mo URL, doc text hoac chup anh trang. Singleton browser, lazy init.
**Han che:** Chi doc, khong tuong tac. Text cat o 5000 ky tu.

---

### 3. screenshot — Chup man hinh
| | |
|---|---|
| **File** | `backend/app/tools/screenshot.py` |
| **Safety** | AUTO |
| **Engine** | mss + Pillow |

**Parameters:**
- `region` (object, optional) — `{left, top, width, height}` hoac full screen

**Kha nang:** Chup toan man hinh hoac vung chi dinh, tra ve base64 PNG.
**Han che:** Chi man hinh chinh, khong multi-monitor. One-shot, khong stream video.

---

### 4. desktop_control — Dieu khien chuot/ban phim
| | |
|---|---|
| **File** | `backend/app/tools/desktop_control.py` |
| **Safety** | NOTIFY |
| **Engine** | PyAutoGUI |

**Parameters:**
- `action` — `click`, `double_click`, `right_click`, `type`, `hotkey`, `scroll`, `move`
- `x`, `y` (int) — toa do cho click/move
- `text` (string) — van ban cho type
- `keys` (string) — to hop phim cho hotkey (vd: `ctrl+c`)
- `amount` (int, default 3) — so dong scroll

**Kha nang:** Click, go phim, hotkey, scroll. Tu dong chup screenshot xac nhan sau moi action.
**Han che:** Khong co drag-and-drop. Chi hoat dong theo toa do pixel, khong nhan dien UI element.

---

### 5. browser_control — Tuong tac web qua DOM
| | |
|---|---|
| **File** | `backend/app/tools/browser_control.py` |
| **Safety** | NOTIFY |
| **Engine** | Playwright (visible browser, 1280x800) |

**Parameters:**
- `action` — `goto`, `click_text`, `fill`, `get_text`, `screenshot`, `wait`
- `url` (string) — URL cho goto
- `text` (string) — text de click/fill
- `selector` (string) — CSS selector (optional)
- `seconds` (number, default 1) — thoi gian wait

**Kha nang:** Dieu huong, click theo text, dien form, doc text, chup anh trang.
**Han che:** Khong hover, khong download file, khong keyboard shortcuts trong trang.

---

### 6. file_manager — Doc/Ghi file
| | |
|---|---|
| **File** | `backend/app/tools/file_manager.py` |
| **Safety** | AUTO (read) / CONFIRM (write) / BLOCK (system paths) |

**Parameters:**
- `action` — `read`, `write`, `list`, `exists`
- `path` (string) — duong dan tuyet doi
- `content` (string) — noi dung ghi (cho write)

**Kha nang:** Doc file (max 1MB), ghi file (tu tao thu muc cha), liet ke thu muc (max 200 entries).
**Han che:** Khong doc file binary. Khong truy cap C:\Windows, C:\Program Files, /etc, /usr.

---

### 7. app_launcher — Mo ung dung
| | |
|---|---|
| **File** | `backend/app/tools/app_launcher.py` |
| **Safety** | NOTIFY |
| **Whitelist** | notepad, calc, chrome, edge, firefox, vscode, explorer, cmd, powershell |

**Parameters:**
- `app` (string) — ten ung dung (case-insensitive)

**Kha nang:** Mo ung dung trong whitelist bang subprocess.
**Han che:** Khong truyen argument, khong theo doi process, chi whitelist.

---

### 8. rag_search — Tim kiem tai lieu da upload
| | |
|---|---|
| **File** | `backend/app/tools/rag_search.py` |
| **Safety** | AUTO |
| **Engine** | ChromaDB + sentence-transformers (local) |

**Parameters:**
- `query` (string) — cau hoi tim kiem
- `top_k` (int, default 5) — so ket qua

**Kha nang:** Tim kiem ngu nghia trong tai lieu da upload, tra ve chunks + citations.
**Han che:** Chi tai lieu da index. Khong full-text search.

---

## Bang tom tat

| Tool | Loai | Safety | Read-only | Interactive |
|------|------|--------|-----------|-------------|
| web_search | Tim kiem | AUTO | Co | Khong |
| web_browser | Duyet web | AUTO/NOTIFY | Co | Khong |
| screenshot | Chup hinh | AUTO | Co | Khong |
| desktop_control | Tu dong hoa | NOTIFY | Khong | Co |
| browser_control | Web DOM | NOTIFY | Khong | Co |
| file_manager | File I/O | AUTO/CONFIRM | Mot phan | Co |
| app_launcher | He thong | NOTIFY | Khong | Co |
| rag_search | Tai lieu | AUTO | Co | Khong |

---

## De xuat tool moi

### Uu tien cao — Gia tri su dung lon, kha thi ngay

#### 9. email_reader — Doc email
| | |
|---|---|
| **Do kho** | Trung binh |
| **Thu vien** | `google-api-python-client` (Gmail API) hoac `imaplib` (IMAP generic) |
| **Safety** | AUTO (doc) / CONFIRM (gui) |

**Kha nang de xuat:**
- `list_emails(folder, limit)` — liet ke email moi nhat
- `read_email(id)` — doc noi dung email cu the
- `search_emails(query, from, after)` — tim email theo tu khoa/nguoi gui/ngay
- `send_email(to, subject, body)` — gui email (can CONFIRM)
- `summarize_inbox()` — tom tat inbox hom nay

**Use cases:** "Hom nay co email nao quan trong khong?", "Doc email tu boss gui hom qua", "Gui email cho X noi dung Y"

---

#### 10. image_generator — Tao hinh anh bang AI
| | |
|---|---|
| **Do kho** | De |
| **Thu vien** | OpenAI DALL-E API / Stability AI / Gemini Imagen |
| **Safety** | CONFIRM (tao file) |

**Kha nang de xuat:**
- `generate(prompt, size, style)` — tao hinh tu mo ta
- `edit(image_path, prompt)` — chinh sua hinh co san
- `save(output_path)` — luu vao thu muc chi dinh

**Use cases:** "Tao hinh logo cho du an", "Ve minh hoa cho bai viet", "Tao avatar cho profile"

---

#### 11. clipboard — Doc/Ghi clipboard
| | |
|---|---|
| **Do kho** | De |
| **Thu vien** | `pyperclip` hoac `win32clipboard` |
| **Safety** | AUTO (doc) / NOTIFY (ghi) |

**Kha nang de xuat:**
- `read()` — doc noi dung clipboard hien tai
- `write(text)` — ghi text vao clipboard
- `read_image()` — doc hinh tu clipboard (screenshot paste)

**Use cases:** "Doc cai toi vua copy", "Copy ket qua nay vao clipboard"

---

#### 12. shell_command — Chay lenh terminal
| | |
|---|---|
| **Do kho** | De (nhung can bao mat ky) |
| **Thu vien** | `asyncio.create_subprocess_exec` |
| **Safety** | CONFIRM (tat ca) / BLOCK (nguy hiem) |

**Kha nang de xuat:**
- `run(command, cwd, timeout)` — chay lenh shell, tra ve stdout/stderr
- Whitelist an toan: `git`, `npm`, `pip`, `python`, `node`, `docker`, `ls`, `dir`, `cat`
- Blacklist cung: `rm -rf /`, `format`, `shutdown`, `del /s`
- Timeout mac dinh 30s

**Use cases:** "Chay git status", "Build project", "Chay test", "Kiem tra Docker containers"

---

#### 13. notification — Thong bao he thong
| | |
|---|---|
| **Do kho** | De |
| **Thu vien** | `plyer` hoac `win10toast` |
| **Safety** | NOTIFY |

**Kha nang de xuat:**
- `send(title, message, icon)` — hien thi OS notification
- `schedule(title, message, delay_seconds)` — hen thong bao

**Use cases:** "Nhac toi hop luc 3h chieu", "Thong bao khi build xong"

---

### Uu tien trung binh — Huu ich cho workflow cu the

#### 14. calendar — Lich Google Calendar
| | |
|---|---|
| **Do kho** | Trung binh |
| **Thu vien** | `google-api-python-client` (Calendar API) |
| **Safety** | AUTO (doc) / CONFIRM (tao/sua/xoa) |

**Kha nang de xuat:**
- `list_events(date, days)` — liet ke su kien
- `create_event(title, start, end, description)` — tao su kien
- `delete_event(id)` — xoa su kien

**Use cases:** "Hom nay co lich gi?", "Dat lich hop voi team luc 2h"

---

#### 15. code_runner — Chay code truc tiep
| | |
|---|---|
| **Do kho** | Trung binh |
| **Thu vien** | `subprocess` + sandbox |
| **Safety** | CONFIRM |

**Kha nang de xuat:**
- `run_python(code)` — chay Python code trong sandbox
- `run_javascript(code)` — chay JS qua Node.js
- `run_godot(project_path, scene)` — chay Godot project, chup screenshot ket qua

**Use cases:** "Chay doan code nay xem ket qua", "Test scene nay trong Godot", "Tinh toan bieu thuc nay"

---

#### 16. http_client — Goi API bat ky
| | |
|---|---|
| **Do kho** | De |
| **Thu vien** | `httpx` (async) |
| **Safety** | NOTIFY (GET) / CONFIRM (POST/PUT/DELETE) |

**Kha nang de xuat:**
- `request(method, url, headers, body)` — goi HTTP request bat ky
- `graphql(url, query, variables)` — goi GraphQL

**Use cases:** "Goi API nay lay du lieu", "Test endpoint moi tao", "Check status cua service"

---

#### 17. ocr — Doc text tu hinh anh
| | |
|---|---|
| **Do kho** | De |
| **Thu vien** | `pytesseract` hoac Gemini Vision |
| **Safety** | AUTO |

**Kha nang de xuat:**
- `extract_text(image_path)` — doc text tu file hinh
- `extract_from_screen(region)` — chup man hinh + OCR ngay

**Use cases:** "Doc text trong hinh nay", "Chup man hinh va doc noi dung"

---

#### 18. audio_player — Phat am thanh
| | |
|---|---|
| **Do kho** | De |
| **Thu vien** | `playsound` hoac `pygame.mixer` |
| **Safety** | NOTIFY |

**Kha nang de xuat:**
- `play(file_path)` — phat file audio
- `tts_save(text, output_path)` — text-to-speech luu file
- `stop()` — dung phat

**Use cases:** "Phat nhac nay", "Doc van ban nay thanh file MP3"

---

### Uu tien thap — Niche nhung an tuong

#### 19. system_info — Thong tin he thong
| | |
|---|---|
| **Do kho** | De |
| **Thu vien** | `psutil`, `platform` |
| **Safety** | AUTO |

**Kha nang de xuat:**
- `get_info()` — CPU, RAM, disk, OS, IP, uptime
- `list_processes(sort_by)` — liet ke process dang chay
- `kill_process(pid)` — tat process (CONFIRM)

**Use cases:** "May tinh dang dung bao nhieu RAM?", "Process nao dang ngon CPU?"

---

#### 20. git_tool — Thao tac Git
| | |
|---|---|
| **Do kho** | Trung binh |
| **Thu vien** | `gitpython` hoac subprocess git |
| **Safety** | AUTO (status/log) / CONFIRM (commit/push) |

**Kha nang de xuat:**
- `status(repo_path)` — git status
- `log(repo_path, limit)` — git log
- `commit(repo_path, message)` — git add + commit
- `push(repo_path)` — git push
- `diff(repo_path)` — git diff

**Use cases:** "Git status cua project nay", "Commit thay doi voi message X"

---

#### 21. database_query — Truy van database
| | |
|---|---|
| **Do kho** | Trung binh |
| **Thu vien** | `asyncpg` (Postgres), `aiosqlite` (SQLite) |
| **Safety** | AUTO (SELECT) / CONFIRM (INSERT/UPDATE/DELETE) / BLOCK (DROP/TRUNCATE) |

**Kha nang de xuat:**
- `query(connection_string, sql)` — chay SQL query
- `list_tables(connection_string)` — liet ke tables
- `describe_table(connection_string, table)` — xem schema

**Use cases:** "Xem du lieu trong bang users", "Chay query nay"

---

#### 22. translator — Dich ngon ngu
| | |
|---|---|
| **Do kho** | De |
| **Thu vien** | `deep-translator` hoac LLM |
| **Safety** | AUTO |

**Kha nang de xuat:**
- `translate(text, from_lang, to_lang)` — dich van ban
- `detect_language(text)` — nhan dien ngon ngu

**Use cases:** "Dich doan nay sang tieng Anh", "Van ban nay ngon ngu gi?"

---

#### 23. pdf_tool — Thao tac PDF
| | |
|---|---|
| **Do kho** | De |
| **Thu vien** | `pypdf2`, `reportlab` |
| **Safety** | AUTO (doc) / CONFIRM (tao/sua) |

**Kha nang de xuat:**
- `read(path, pages)` — doc text tu PDF
- `merge(paths, output)` — gop nhieu PDF
- `split(path, pages, output)` — tach trang
- `to_images(path, output_dir)` — chuyen PDF thanh hinh

**Use cases:** "Doc file PDF nay", "Gop 3 file PDF lai", "Chuyen PDF thanh hinh"

---

## Lo trinh de xuat

| Phase | Tools | Ly do |
|-------|-------|-------|
| **Phase 12** | clipboard, shell_command, notification | De lam, gia tri cao, tang kha nang tu dong hoa desktop |
| **Phase 13** | email_reader, calendar | Ket noi Google Workspace, bien JARVIS thanh tro ly that su |
| **Phase 14** | image_generator, ocr | Xu ly hinh anh — tao + doc |
| **Phase 15** | code_runner, http_client | Developer tools — chay code, test API |
| **Phase 16** | system_info, git_tool, pdf_tool | Tien ich nang cao |
| **Phase 17** | database_query, translator, audio_player | Niche tools |

---

## Cach them tool moi

1. Tao file `backend/app/tools/<ten_tool>.py`
2. Ke thua `BaseTool`, dinh nghia `name`, `description`, `parameters` (JSON Schema)
3. Implement `async execute(**kwargs) -> ToolResult`
4. Dang ky trong `backend/app/tools/__init__.py` > `create_default_registry()`
5. Cap nhat safety rules trong `safety.py` neu can
6. Cap nhat system prompt trong `agent/prompts.py`
7. Viet tests trong `backend/tests/`
