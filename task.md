# JARVIS AI Assistant - Quản lý Tiến độ

> Cập nhật lần cuối: 15/04/2026

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

- [ ] E2E Testing với Playwright
- [ ] Performance optimization (streaming latency, tool execution time)
- [ ] Error handling toàn diện (retry, fallback, user-friendly messages)
- [ ] Security audit (API key protection, input sanitization, sandbox tool execution)
- [ ] Documentation sync (cập nhật README, technical docs)
- [ ] Demo video / screenshots
