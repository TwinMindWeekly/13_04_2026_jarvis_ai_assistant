# JARVIS AI Assistant - Quản lý Tiến độ

> Cập nhật lần cuối: 15/04/2026

---

## Phase 1: Nền tảng Backend & LLM Provider Factory
> Mục tiêu: Xây dựng backend FastAPI với khả năng gọi LLM đa nhà cung cấp

- [ ] Khởi tạo project FastAPI với cấu trúc thư mục chuẩn
- [ ] Thiết kế và triển khai LLM Provider Factory (OpenAI, Gemini, Claude, Ollama)
- [ ] Xây dựng API endpoint `/api/chat` cơ bản (text in → text out)
- [ ] Cấu hình môi trường (.env, settings, CORS)
- [ ] Viết Unit Test cho LLM Factory

---

## Phase 2: Tool Registry & Agent Brain
> Mục tiêu: Xây dựng hệ thống tool và agent có khả năng suy luận + gọi tool

- [ ] Thiết kế Tool Registry (interface chuẩn cho mọi tool)
- [ ] Triển khai tool: `web_search` (Google/Bing Search API)
- [ ] Triển khai tool: `web_browser` (Playwright - mở URL, đọc nội dung, chụp ảnh)
- [ ] Triển khai tool: `screenshot` (chụp màn hình desktop)
- [ ] Xây dựng Agent Brain với LangGraph (Planner → Executor → Reviewer loop)
- [ ] API endpoint `/api/agent/execute` (nhận yêu cầu → agent tự chọn tool → trả kết quả)
- [ ] Viết Integration Test cho Agent workflow

---

## Phase 3: Frontend Chat & Action Viewer
> Mục tiêu: Giao diện người dùng hiện đại với khả năng hiển thị hành động agent

- [ ] Khởi tạo React + Vite project
- [ ] Thiết kế UI: Chat interface (glassmorphism, dark mode)
- [ ] Component: MessageBubble (text, markdown, code block, image)
- [ ] Component: ActionViewer (hiển thị tool đang chạy, screenshot, kết quả)
- [ ] Component: SettingsPanel (chọn provider, API key, model)
- [ ] Tích hợp WebSocket cho streaming response
- [ ] Tích hợp REST API cho agent execution
- [ ] i18n (Tiếng Việt / English)

---

## Phase 4: Voice Interface (STT + TTS)
> Mục tiêu: Giao tiếp bằng giọng nói real-time

- [ ] Tích hợp Web Speech API (Speech-to-Text) trên frontend
- [ ] Tích hợp TTS (Text-to-Speech): OpenAI TTS / Google TTS / Browser native
- [ ] UI: Nút microphone, hiệu ứng sóng âm khi nghe/nói
- [ ] Backend: WebSocket endpoint cho voice streaming
- [ ] Wake word detection (tuỳ chọn: "Hey Jarvis")

---

## Phase 5: Computer Use & Advanced Actions
> Mục tiêu: Nâng cấp thành trợ lý có thể thao tác máy tính

- [ ] Triển khai tool: `computer_use` (Claude Computer Use API hoặc PyAutoGUI fallback)
- [ ] Triển khai tool: `file_manager` (đọc/ghi/tìm file trên máy)
- [ ] Triển khai tool: `app_launcher` (mở ứng dụng trên máy)
- [ ] Xây dựng Safety Layer (xác nhận trước khi thực hiện hành động nguy hiểm)
- [ ] UI: Live screen viewer (xem agent thao tác real-time)

---

## Phase 6: RAG Integration
> Mục tiêu: Truy xuất và trả lời dựa trên tài liệu riêng

- [ ] Tích hợp ChromaDB cho vector storage
- [ ] Tool: `rag_search` (tìm kiếm trong tài liệu đã upload)
- [ ] UI: Document upload & management
- [ ] Agent tự quyết định khi nào dùng RAG vs web search

---

## Phase 7: Testing & Polish
> Mục tiêu: Đảm bảo chất lượng và trải nghiệm người dùng

- [ ] E2E Testing với Playwright
- [ ] Performance optimization (streaming latency, tool execution time)
- [ ] Error handling toàn diện (retry, fallback, user-friendly messages)
- [ ] Security audit (API key protection, input sanitization, sandbox tool execution)
- [ ] Documentation sync (cập nhật README, technical docs)
- [ ] Demo video / screenshots
