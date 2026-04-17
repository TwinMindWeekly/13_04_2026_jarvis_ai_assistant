# JARVIS AI Assistant - Quản lý Tiến độ

> Cập nhật lần cuối: 16/04/2026 (Phase 15 complete — 15 tools)

---

## Phase 1: Nền tảng Backend & LLM Provider Factory
> Mục tiêu: Xây dựng backend FastAPI với khả năng gọi LLM đa nhà cung cấp

- [x] Khởi tạo project FastAPI với cấu trúc thư mục chuẩn
- [x] Thiết kế và triển khai LLM Provider Factory (OpenAI, Gemini, Claude, Ollama)
- [x] Xây dựng API endpoint `/api/chat` cơ bản (text in → text out)
- [x] Cấu hình môi trường (.env, settings, CORS)
- [x] Viết Unit Test cho LLM Factory (19/19 passed)

---

## Phase 2: Tool Registry & Agent Brain
> Mục tiêu: Xây dựng hệ thống tool và agent có khả năng suy luận + gọi tool

- [x] Thiết kế Tool Registry (interface chuẩn cho mọi tool)
- [x] Triển khai tool: `web_search` (DuckDuckGo — no API key required)
- [x] Triển khai tool: `web_browser` (Playwright - mở URL, đọc nội dung, chụp ảnh)
- [x] Triển khai tool: `screenshot` (chụp màn hình desktop)
- [x] Xây dựng Agent Brain với LangGraph (ReAct loop via create_react_agent)
- [x] API endpoint `/api/agent/execute` + WebSocket `/ws/agent` streaming
- [x] Viết Integration Test cho Agent workflow (60/60 passed)

---

## Phase 3: Frontend Chat & Action Viewer
> Mục tiêu: Giao diện người dùng hiện đại với khả năng hiển thị hành động agent

- [x] Khởi tạo React 19 + Vite 8 + Tailwind CSS v4
- [x] Thiết kế UI: Chat interface (glassmorphism, dark mode, JARVIS aesthetic)
- [x] Component: MessageBubble (text, markdown, code block, streaming cursor)
- [x] Component: ActionViewer + ActionStep (tool timeline, collapsible, shimmer loading)
- [x] Component: SettingsPanel (provider/model dropdown, test connection, language toggle)
- [x] Tích hợp WebSocket cho streaming response (useWebSocket + auto-reconnect)
- [x] Tích hợp REST API cho agent execution (useAgent + REST fallback)
- [x] i18n (Tiếng Việt / English) + Sidebar + App.jsx wiring

---

## Phase 4: Voice Interface (STT + TTS)
> Mục tiêu: Giao tiếp bằng giọng nói real-time

- [x] Tích hợp Web Speech API (Speech-to-Text) trên frontend
- [x] Tích hợp TTS (Text-to-Speech): Browser native SpeechSynthesis
- [x] UI: Nút microphone với pulse animation, transcript preview
- [ ] Backend: WebSocket endpoint cho voice streaming (deferred)
- [ ] Wake word detection (deferred)

---

## Phase 5: Computer Use & Advanced Actions
> Mục tiêu: Nâng cấp thành trợ lý có thể thao tác máy tính

- [x] Triển khai tool: `desktop_control` (PyAutoGUI + screenshot verify)
- [x] Triển khai tool: `browser_control` (Playwright DOM-based, OpenClaw-style)
- [x] Triển khai tool: `file_manager` (pathlib, with safety checks)
- [x] Triển khai tool: `app_launcher` (subprocess, whitelist-based)
- [x] Xây dựng Safety Layer (4 levels: AUTO/NOTIFY/CONFIRM/BLOCK)
- [x] Update agent prompt + register all 7 tools
- [x] Tests: 105/105 passed (45 new + 60 existing)
- [ ] UI: Live screen viewer (deferred — sẽ làm ở Phase 7 polish)

---

## Phase 6: RAG Integration
> Mục tiêu: Truy xuất và trả lời dựa trên tài liệu riêng

- [x] Tích hợp ChromaDB cho vector storage (PersistentClient + sentence-transformers local embeddings)
- [x] Tool: `rag_search` — tìm kiếm trong docs đã upload (tool 8)
- [x] UI: Document upload & management (DocumentsPanel modal, sidebar button)
- [x] Agent tự quyết: rag_search ưu tiên hơn web_search khi có docs (system prompt updated)
- [x] API: POST /api/documents/upload, GET /api/documents, DELETE /api/documents/:id
- [x] Document parser: PDF, DOCX, TXT, MD, PPTX, XLSX (unstructured)
- [x] Tests: 127/127 passed (22 mới)

---

## Phase 7: Testing & Polish
> Mục tiêu: Đảm bảo chất lượng và trải nghiệm người dùng

- [x] Documentation sync — README + technical_reference rewrite cho khớp 8 tools, Bootstrap, Gemini 2.5
- [x] Known issues log — ghi 8 bug đã fix (DDG v8, Gemini deprecated, voice echo loop, thinking format leak, safety filter, start.bat ERRORLEVEL, PDF tracking, frontend retry)
- [x] Error handling — useAgent retry 3 lần exponential backoff, react-bootstrap Toast, WS auto-reconnect 5 lần
- [x] Backend startup health checks — kiểm tra API keys, ChromaDB writable, Playwright importable
- [x] Performance — Playwright lazy load (singleton _ensure_browser, deferred tới lần đầu tool dùng)
- [x] Cleanup — verify không còn debug/scratch files, .gitignore đầy đủ
- [x] E2E Testing — Playwright config + 3 critical flows (app load, settings panel, documents panel)
- [ ] Security audit toàn diện (deferred — out of scope)
- [ ] Demo video / screenshots (deferred — out of scope)

---

## Phase 8: Knowledge Graph (Obsidian-style)
> Mục tiêu: Hiển thị mối quan hệ giữa các tài liệu RAG dưới dạng đồ thị tương tác.

- [x] Research — so sánh Sigma.js / react-force-graph / Reagraph / Cytoscape / NetV.js, chọn react-force-graph-2d
- [x] Backend graph builder — mean embedding per doc + cosine pairwise + threshold filter
- [x] Backend graph router — GET /api/graph/data, /stats, POST /rebuild
- [x] Cache layer — JSON file, key hash(doc_ids + threshold), invalidate on upload/delete
- [x] Frontend GraphPanel — ForceGraph2D Canvas với drag/zoom/pan/click/hover
- [x] GraphToolbar — search filter, threshold slider (debounce 300ms), zoom-to-fit, rebuild
- [x] GraphDetailPanel — filename, folder, chunks, uploaded date, neighbors sorted by similarity
- [x] GraphLegend — color map folders → node colors
- [x] Performance — cooldownTicks=120, nodePointerAreaPaint hit area lớn, label chỉ hiện khi zoom
- [x] Tests — 12 backend unit tests (cosine, cache, builder edge cases) + 1 E2E test
- [x] Docs — README + technical_reference + phase8_research + phase8_implementation_plan

---

## Phase 9: Graph View Redesign — Obsidian 3-Panel Layout + AI Chat
> Mục tiêu: Chuyển Knowledge Graph từ modal popup → full-page 3-panel layout giống Obsidian, tích hợp AI chat sidebar để query tài liệu ngay trong graph view.

- [x] Thiết kế layout 3 panel: Left (search/docs) + Center (graph canvas) + Right (AI chat)
- [x] GraphPage.jsx (mới) — container 3-column page view thay thế GraphPanel modal
- [x] GraphLeftPanel.jsx (mới) — search box, document list, detail/neighbors khi click node
- [x] GraphChatPanel.jsx (mới) — AI chat sidebar dùng /api/agent/execute + rag_search, highlight nodes
- [x] GraphCanvas.jsx (mới) — ForceGraph2D tách riêng, AI highlight ring, floating zoom-to-fit
- [x] App.jsx — viewMode state ('chat'|'graph'), render GraphPage thay vì modal
- [x] Xoá GraphToolbar.jsx, GraphPanel.jsx, GraphDetailPanel.jsx (merge vào components mới)
- [x] Cập nhật main.css — ~300 dòng graph page dark theme, 3-panel layout, responsive
- [x] useGraph.js — đơn giản hoá: bỏ threshold/rebuild, hardcode 0.5
- [x] AI chat trong graph: user hỏi → agent dùng rag_search → highlight related nodes
- [x] Click node → detail + neighbors trong left panel
- [x] Graph canvas: nền đen #0f1014, ForceGraph2D, floating Fit button
- [x] i18n — 8 keys mới cho graph page vào en.json + vi.json
- [ ] Docs sync — cập nhật technical_reference.md, README.md
- [ ] E2E test — Playwright test cho graph page layout mới

---

## Phase 10: AI Auto-Convert Pipeline — Wikilinks Only Graph
> Mục tiêu: Upload PDF/DOCX → AI tự convert sang .md + chèn [[wikilinks]] → graph chỉ dùng explicit wikilink edges + backlinks. Bỏ cosine similarity edges.

- [ ] Install MarkItDown dependency
- [ ] Backend: `rag/md_converter.py` — MarkItDown wrapper, convert PDF/DOCX/PPTX/XLSX → clean .md
- [ ] Backend: `rag/wikilink_generator.py` — LLM prompt chèn [[wikilinks]] vào markdown + chunking cho file lớn
- [ ] Backend: `graph/link_extractor.py` — regex parse [[Target]] và [[Target|Display]] từ .md
- [ ] Backend: vault storage — lưu .md vào `backend/uploads/vault/{doc_id}.md`
- [ ] Backend: `routers/vault.py` — GET /api/vault/{doc_id} xem nội dung .md
- [ ] Sửa `routers/documents.py` — upload pipeline thêm background task: convert + LLM wikilinks
- [ ] Sửa `graph/builder.py` — xoá cosine similarity, chỉ dùng wikilink edges + backlinks
- [ ] Sửa `models/graph_schemas.py` — GraphLink thêm context field
- [ ] Frontend: GraphLeftPanel — hiện backlinks section khi click node
- [ ] Fallback: nếu không có LLM key → bỏ qua wikilink step, graph trống (chỉ orphan nodes)
- [x] Install MarkItDown dependency
- [x] Backend: `rag/md_converter.py` — MarkItDown wrapper
- [x] Backend: `rag/wikilink_generator.py` — LLM prompt + chunking
- [x] Backend: `graph/link_extractor.py` — regex parse [[wikilinks]]
- [x] Backend: vault storage + `routers/vault.py` — GET /api/vault/{doc_id}
- [x] Sửa `routers/documents.py` — background task pipeline
- [x] Sửa `graph/builder.py` — wikilink-only edges, bỏ cosine similarity
- [x] Sửa `models/graph_schemas.py` — GraphLink + context field
- [x] Tách config: WIKILINK_PROVIDER=ollama (local free) vs DEFAULT_PROVIDER (cloud)
- [x] Ollama preload model on startup (background thread) + unload on shutdown
- [x] Auto-fallback provider chain: groq → gemini → sambanova → openai → claude → ollama
- [x] Groq + SambaNova providers thêm vào _build_llm() (free tier, tool calling)
- [x] Runtime retry: agent execution hit quota → auto switch next provider
- [x] Test: Groq Llama 3.3 70B auto-fallback hoạt động, wikilinks pipeline verified
- [ ] Tests — unit tests cho link_extractor, wikilink_generator, md_converter
- [ ] Docs sync — technical_reference.md, README.md, task.md

---

## Phase 11: Provider Usage Dashboard
> Mục tiêu: Hiển thị usage (requests, tokens) của tất cả LLM providers, quota limits, thời gian reset trong Settings panel.

- [ ] Backend: `services/usage_tracker.py` — singleton tracker đếm requests/tokens per provider, persist JSON
- [ ] Backend: parse rate-limit headers từ Groq/SambaNova/OpenAI responses (x-ratelimit-remaining-*)
- [ ] Backend: `routers/usage.py` — GET /api/usage endpoint trả stats tất cả providers
- [ ] Frontend: SettingsPanel thêm "Usage" tab — bảng hiện mỗi provider: requests used/limit, tokens, reset time
- [ ] Frontend: hiện provider đang dùng (auto → "Using: Groq / llama-3.3-70b") trong chat header
- [ ] Reset logic: daily counter reset midnight UTC, RPM counter rolling 60s
- [ ] i18n — keys mới cho usage dashboard
- [ ] Docs sync

---

## Phase 12: Chat File Upload (Inline Attachments)
> Mục tiêu: User đính kèm file trực tiếp vào chat (như ChatGPT), agent đọc và phân tích inline.

- [x] Backend: `routers/attachments.py` — POST /api/agent/upload-attachment (parse file, trả text)
- [x] Backend: `models/attachment_schemas.py` — response schema
- [x] Backend: Mở rộng document_parser.py hỗ trợ thêm .py, .js, .ts, .json, .csv, .html, .css, .yaml, .xml, .log
- [x] Backend: Giới hạn 5MB/file, tối đa 3 files/message, text cap 100K chars
- [x] Frontend: `hooks/useAttachments.js` — quản lý state attachments
- [x] Frontend: `components/AttachmentPreview.jsx` — hiện pill badges file đã chọn
- [x] Frontend: Wire nút "+" trong ChatArea → file picker + drag-and-drop
- [x] Frontend: useAgent.js serialize attachments vào message
- [x] Frontend: Cancel request (AbortController) + cancel button UI
- [x] Frontend: Language toggle (EN/VI) trong header
- [x] Skill system: auto-load .md skills vào prompt + skill_manager tool
- [x] Tests — backend upload endpoint + test assertions updated (148/148 pass)
- [ ] Docs sync

---

## Phase 13: Shell, Clipboard, Notification Tools
> Mục tiêu: 3 tools mới cho desktop power users — shell command là tool có impact cao nhất.

- [x] Backend: `tools/shell_exec.py` — chạy lệnh terminal (CONFIRM), timeout 30-120s, blocked patterns
- [x] Backend: `tools/clipboard.py` — đọc/ghi clipboard (AUTO/NOTIFY)
- [x] Backend: `tools/system_notification.py` — thông báo OS (NOTIFY)
- [x] Backend: Mở rộng safety.py — thêm blocked patterns cho shell
- [x] Backend: Cập nhật prompts.py — thêm 3 tool docs
- [x] Backend: Cài pyperclip, plyer
- [x] Tests — shell_exec, clipboard, system_notification
- [ ] Docs sync

---

## Phase 14: Email Tool (Read & Send)
> Mục tiêu: Đọc/gửi email qua IMAP/SMTP — hoạt động với Gmail App Password, Outlook, Yahoo.

- [x] Backend: `tools/email_tool.py` — actions: read_inbox, read_email, search, send (CONFIRM)
- [x] Backend: `services/email_client.py` — IMAP/SMTP sync client wrapped in asyncio.to_thread
- [x] Backend: Config .env — IMAP_HOST/PORT/USER/PASSWORD, SMTP_HOST/PORT/USER/PASSWORD
- [x] Backend: Cài aioimaplib, aiosmtplib
- [x] Backend: skills/email.md — skill triggers
- [x] Tests — email tool với mocked connections
- [ ] Docs sync

---

## Phase 15: Image Generation + Code Runner
> Mục tiêu: Tạo hình ảnh AI + chạy code trực tiếp (Python, JS, Godot).

- [x] Backend: `tools/image_generator.py` — DALL-E 3 API, lưu uploads/generated/
- [x] Backend: `tools/code_runner.py` — chạy Python/JS/TS/Bash/PowerShell/Godot
- [x] Backend: `routers/files.py` — serve generated images
- [x] Backend: Config — GODOT_PATH, STABILITY_API_KEY
- [x] Frontend: MessageBubble hiện inline image khi response chứa image path
- [x] Tests — image_generator (mocked API), code_runner
- [ ] Docs sync

---

## Phase 16: SQLite foundation + doc_query tool
> Mục tiêu: Thay `uploads/documents_metadata.json` bằng SQLite (SQLAlchemy 2 async) làm nền móng cho multi-Gmail + Profile/Jobs. Agent query metadata/wikilinks qua tool thay vì push toàn bộ JSON vào prompt.

- [x] Backend: `app/db/{__init__,connection,models}.py` — DeclarativeBase, 7 tables (documents, wikilinks, email_accounts, email_messages + FTS5 virtual table, user_profile, jobs, saved_job_searches), WAL + foreign_keys via event listener
- [x] Backend: `app/db/migrate_json.py` — idempotent JSON → SQLite migration, rename file tới `.migrated`
- [x] Backend: `app/db/services/documents.py` — CRUD + wikilink resolver, replaces JSON-based `_load_metadata/_save_metadata`
- [x] Backend: `app/routers/documents.py`, `app/routers/vault.py` — DB-backed
- [x] Backend: `app/graph/builder.py` — JOIN documents/wikilinks, no more JSON load
- [x] Backend: `app/tools/doc_query.py` — actions `find_by_wikilink`, `find_backlinks`, `list_by_folder`, `list_all`, `get_metadata`, `read_doc`
- [x] Backend: `app/main.py` lifespan — `init_db` + `migrate_json_if_needed`
- [x] Tests — documents/graph/doc_query/migration

---

## Phase 17: Multi-Gmail accounts + FTS5 cache
> Mục tiêu: Nhiều tài khoản Gmail cùng lúc, hỏi theo ngày/người gửi/quan trọng. Password mã hoá Fernet.

- [x] Backend: `app/services/secrets.py` — Fernet key auto-gen + persist vào `.env`, encrypt/decrypt string helpers
- [x] Backend: `app/db/services/email_accounts.py` — CRUD + test IMAP connection + encrypted passwords
- [x] Backend: `app/routers/email_accounts.py` — GET/POST/PATCH/DELETE + POST `/{id}/test`
- [x] Backend: `app/services/email_client.py` — `EmailClient(credentials)` per account, new search actions (date, sender, important)
- [x] Backend: `app/tools/email_tool.py` — `account=` param, actions `list_accounts`, `search_by_date`, `search_by_sender`, `search_important`, `search_cached` (FTS5)
- [x] Backend: `app/services/email_sync.py` — APScheduler job pulls recent UIDs mỗi `email_sync_interval_minutes`, upsert `email_messages` (FTS5 triggers auto-sync)
- [x] Frontend: `EmailAccountsSection.jsx` + tab "Email" trong SettingsPanel — add/edit/delete/test, toggle default/sync
- [x] Tests — encryption round-trip, CRUD, resolve by label, tool dispatcher

---

## Phase 18: User Profile + Job Search
> Mục tiêu: Trang Profile upload CV, tool tự tìm việc phù hợp ngành/kỹ năng user từ 6 source.

- [x] Backend: `app/db/services/user_profile.py` — singleton upsert, skills/titles/locations as JSON arrays
- [x] Backend: `app/services/cv_extractor.py` — LLM trích skills/titles/locations từ CV text (uses `build_llm_with_fallback`)
- [x] Backend: `app/routers/profile.py` — GET/PUT `/api/profile`, POST `/api/profile/upload` (parse via DocumentParser + CV extractor)
- [x] Backend: `app/services/job_sources/{duckduckgo,topcv,itviec,vietnamworks,remoteok,weworkremotely}.py` — mỗi source defensive try/except trả []
- [x] Backend: `app/services/jobs_matcher.py` — Jaccard skill overlap + location/remote bonus → score 0..1
- [x] Backend: `app/db/services/jobs.py` — list/save CRUD, `refresh_jobs` (saved searches) + `refresh_from_profile_defaults`, `purge_old_jobs`
- [x] Backend: `app/routers/jobs.py` — list/refresh/save/unsave + saved-searches CRUD
- [x] Backend: `app/tools/job_search.py` — actions `list_tracked`, `search`, `refresh`, `save`, `unsave`
- [x] Backend: APScheduler daily `jobs_refresh` job (configurable via `jobs_refresh_interval_minutes`, default 1440)
- [x] Frontend: `ProfilePage.jsx` (CV upload + chip editors) + `JobsPage.jsx` (saved searches, filters, match_score badge, save/open)
- [x] Frontend: Sidebar — 2 nav items (Profile, Jobs) trên Knowledge Graph
- [x] Frontend: App.jsx viewMode thêm `profile` | `jobs`
- [x] Tests — matcher Jaccard, profile upsert, saved-search CRUD, refresh flow
- [ ] Docs sync

---

## Phase 19: Nâng cấp tìm kiếm ngang Grok (Search Parity)
> Mục tiêu: Bổ sung operator filter cho `web_search`, action `summarize` cho `web_browser`, và tool `x_search` mới để tìm kiếm X/Twitter với 3 tầng fallback. Đổi `_build_llm` → `build_llm` (public) để tái sử dụng liên module.
> Hoàn thành: 17/04/2026

- [x] Backend: `app/tools/web_search.py` — thêm params tuỳ chọn `site`, `exact_phrase`, `exclude`, `filetype`, `date_range`, `region`, `safe_search`, `rerank` (ngang tính năng Grok search). Output mỗi kết quả bổ sung field tuỳ chọn `date` và `score`.
- [x] Backend: `app/tools/web_browser.py` — thêm action `summarize` với params `instructions` và `max_chars`. Dùng `build_llm_with_fallback` để tóm tắt nội dung trang bằng LLM (tương đương Grok `browse_page`).
- [x] Backend: `app/tools/x_search.py` — tool mới `XSearchTool`. Actions: `keyword_search`, `user_search`, `thread_fetch`, `semantic_search`. Fallback 3 tầng: twscrape (Tier 1) → Nitter RSS (Tier 2) → `web_search(site:x.com)` (Tier 3). Metadata luôn có `tier_used`.
- [x] Backend: `app/agent/brain.py` — đổi tên `_build_llm` → `build_llm` (public) để các module khác (`cv_extractor`, `web_browser` summarize) có thể dùng trực tiếp.
- [x] Backend: `app/core/config.py` — thêm `twscrape_accounts_file: str = ""` và `x_nitter_instances: list[str]` (4 Nitter instance mặc định).
- [x] Backend: `requirements.txt` — thêm `twscrape>=0.17` và `feedparser>=6.0`.
- [x] Registry: `create_default_registry()` đăng ký `XSearchTool` sau `JobSearchTool`. Tổng số tool: 18.
- [x] Docs sync — CLAUDE.md, task.md, README.md, docs/technical_reference.md
