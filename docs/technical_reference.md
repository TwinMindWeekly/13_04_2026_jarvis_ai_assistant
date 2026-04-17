# JARVIS AI Assistant - Technical Reference

> Tài liệu kỹ thuật chi tiết về kiến trúc, API, và luồng dữ liệu.
> Cập nhật lần cuối: 16/04/2026 (Phase 15 complete)

---

## 1. Kiến trúc tổng quan

### Mô hình kiến trúc: Agent-based Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      CLIENT (React 19 + Vite 8)                      │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────────────┐  │
│  │ ChatArea │  │ ActionViewer │  │ DocumentsPanel (RAG)           │  │
│  │ Sidebar  │  │ SettingsPanel│  │ AttachmentPreview (pill badges) │  │
│  │          │  │              │  │ VoiceButton                    │  │
│  └────┬─────┘  └──────┬───────┘  └──────────────┬─────────────────┘  │
│       └────────────────┴───────────────────────────┘                  │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  GraphPage.jsx — 3-panel Obsidian layout                       │   │
│  │  GraphLeftPanel │ GraphCanvas (react-force-graph-2d) │ ChatArea│   │
│  └────────────────────────────────────────────────────────────────┘   │
│  React hooks: useAgent, useWebSocket, useVoice, useSettings,          │
│               useAttachments, useGraph, useDocTree                    │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ REST + SSE + WebSocket
                  ┌────────▼───────────────────────┐
                  │     FastAPI Server (8000)       │
                  ├─────────────────────────────────┤
                  │ Routers:                        │
                  │ ├── /api/chat                   │  (direct LLM, SSE stream)
                  │ ├── /api/agent/execute          │  (REST, ReAct loop)
                  │ ├── /api/agent/upload-attachment│  (ephemeral file attach)
                  │ ├── /ws/agent                  │  (WebSocket streaming)
                  │ ├── /api/providers             │  (list / test)
                  │ ├── /api/documents             │  (RAG upload/list/delete)
                  │ ├── /api/vault                 │  (read/edit vault .md)
                  │ ├── /api/files/generated       │  (serve DALL-E output)
                  │ ├── /api/usage                 │  (provider usage stats)
                  │ └── /api/graph                 │  (knowledge graph)
                  ├─────────────────────────────────┤
                  │ Agent Brain                     │
                  │ LangGraph create_react_agent    │
                  │ (Think→Act→Loop)                │
                  ├─────────────────────────────────┤
                  │ Tool Registry (15 tools)        │
                  │ ├── web_search                  │
                  │ ├── web_browser                 │
                  │ ├── browser_control             │
                  │ ├── screenshot                  │
                  │ ├── desktop_control             │
                  │ ├── file_manager                │
                  │ ├── app_launcher                │
                  │ ├── rag_search                  │
                  │ ├── skill_manager               │
                  │ ├── shell_exec                  │
                  │ ├── clipboard                   │
                  │ ├── system_notification         │
                  │ ├── email                       │
                  │ ├── image_generator             │
                  │ └── code_runner                 │
                  ├─────────────────────────────────┤
                  │ Safety Layer                    │
                  │ AUTO/NOTIFY/CONFIRM/BLOCK       │
                  ├─────────────────────────────────┤
                  │ LLM Factory (6 providers)       │
                  │ ├── OpenAI (proxy support)      │
                  │ ├── Gemini 2.5                  │
                  │ ├── Claude (proxy support)      │
                  │ ├── Groq                        │
                  │ ├── SambaNova                   │
                  │ └── Ollama                      │
                  └─────────────────────────────────┘
```

### Luồng xử lý chính

```
User input (text or voice via SpeechRecognition)
    │
    ▼
[1] /api/agent/execute (POST) hoặc /ws/agent (WebSocket)
    │ Validate qua Pydantic AgentRequest
    ▼
[2] create_agent_brain(provider, model, language, user_message)
    │ → skill_loader.get_prompt_injection(user_message) tự động inject
    │   nội dung skill .md phù hợp vào system prompt
    │ → LangGraph CompiledStateGraph với system prompt đã được bổ sung skill
    ▼
[3] brain.ainvoke / brain.astream_events
    │ ReAct loop: LLM quyết định gọi tool nào
    │ Mỗi tool call → ToolMessage trong state
    ▼
[4] Tool execution với Safety Layer check
    │ Tool trả về string/dict; ToolMessage thêm vào state
    ▼
[5] LLM observe kết quả → quyết định gọi tool tiếp hay reply
    │ Tối đa recursion_limit=10
    ▼
[6] Final response — string (OpenAI/Claude) hoặc list-of-dicts
    │ (Gemini 2.5 trả [{"type":"text","text":"..."}, ...])
    │ Backend extract chỉ block "text", bỏ "thinking"/"signature"
    ▼
[7] Stream về client qua WebSocket events:
    on_tool_start → on_tool_end → on_chat_model_stream
```

---

## 2. API Reference

### REST Endpoints

#### `POST /api/chat`
Direct LLM call (không qua agent, không có tool use).

**Request:**
```json
{
  "messages": [{"role": "user", "content": "Xin chào"}],
  "provider": "openai",
  "model": "gpt-4o-mini",
  "stream": true,
  "temperature": 0.7,
  "max_tokens": 4096
}
```

**Response (SSE khi stream=true):**
```
data: {"content": "Xin", "done": false}
data: {"content": " chào", "done": false}
data: {"content": "", "done": true}
```

#### `POST /api/agent/execute`
Agent execution với khả năng gọi tool.

**Request:**
```json
{
  "message": "Tóm tắt tài liệu Odoo cho tôi",
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "recursion_limit": 10
}
```

**Response:**
```json
{
  "response": "Theo tài liệu, Odoo là...",
  "actions": [
    {
      "step": 1,
      "tool": "rag_search",
      "input": {},
      "output": "[{...}]",
      "status": "completed",
      "duration_ms": 0
    }
  ],
  "provider": "gemini",
  "model": "gemini-2.5-flash"
}
```

#### `POST /api/agent/upload-attachment`
Upload file để phân tích inline trong chat (ephemeral — không index vào ChromaDB).

- **Content-Type**: `multipart/form-data`
- **Field**: `file` (tối đa 5MB, hỗ trợ 43 extension)
- **Response**: `{"filename": "report.pdf", "content": "extracted text...", "char_count": 1234}`
- Nội dung được trích xuất và đính kèm vào system prompt của lượt chat đó; file không lưu lại sau request.

#### `GET /api/providers`
Liệt kê provider + model khả dụng (kiểm tra theo env keys hiện có).

#### `POST /api/providers/test`
Test ping provider, đo latency.

**Request:**
```json
{ "provider": "openai", "api_key": "" }
```

`api_key=""` → backend dùng key trong `.env`. Truyền key khác → test override.

#### `POST /api/documents/upload`
Upload tài liệu vào ChromaDB.

- **Content-Type**: `multipart/form-data`
- **Field**: `file` (PDF/DOCX/TXT/MD/PPTX/XLSX)
- **Response**: `{"doc_id": "uuid", "filename": "...", "chunks": 19}`

#### `GET /api/documents/`
Liệt kê documents đã upload (đọc từ JSON metadata index).

#### `DELETE /api/documents/{doc_id}`
Xoá document khỏi vector store + filesystem + metadata. Tự động invalidate graph cache.

#### `GET /api/vault/{doc_id}`
Đọc file Markdown vault của document đã upload. File được lưu tại `uploads/vault/{doc_id}.md` sau khi qua pipeline MarkItDown + wikilink generator.

**Response:** plain text Markdown.

#### `PUT /api/vault/{doc_id}`
Cập nhật nội dung Markdown vault. Sửa file trên disk; chưa tự động re-extract wikilinks sau khi edit.

**Request body:** `{"content": "# Updated Markdown\n..."}`.

#### `GET /api/files/generated/{filename}`
Phục vụ ảnh sinh ra bởi `image_generator` tool (DALL-E output). Có bảo vệ path traversal — chỉ cho phép filename không chứa `/` hay `..`.

**Response:** image binary (PNG).

#### `GET /api/usage/`
Thống kê usage theo provider: số lần gọi, token tiêu thụ, latency trung bình.

#### `GET /api/graph/data?force=false`
Knowledge Graph data — nodes là documents, edges là wikilinks giữa các vault .md files.

**Response:**
```json
{
  "nodes": [
    {"id": "uuid", "label": "file.pdf", "folder": "", "chunks_count": 19,
     "size_bytes": 378214, "uploaded_at": "2026-04-15T06:51:14", "file_ext": ".pdf"}
  ],
  "links": [
    {"source": "uuid1", "target": "uuid2", "weight": 1.0}
  ],
  "meta": {
    "total_docs": 10, "total_links": 24,
    "generated_at": "2026-04-15T09:00:00+00:00", "cached": true
  }
}
```

- Graph dùng **wikilink edges only** — không còn cosine similarity.
- `force=true` — bỏ qua cache, recompute.
- Cache key = `md5(sorted(doc_ids) + wikilink_count)`; invalidate khi upload/delete document.

#### `GET /api/graph/stats`
Trả counts mà không compute graph. `{total_docs, total_chunks, cache_exists}`.

#### `POST /api/graph/rebuild`
Invalidate cache và rebuild từ đầu.

### WebSocket Endpoints

#### `ws://localhost:8000/ws/agent`
Streaming agent execution real-time.

**Client → Server (init message):**
```json
{
  "message": "Tìm thời tiết Hà Nội",
  "provider": "openai",
  "model": "gpt-4o-mini"
}
```

**Server → Client (sequence of events):**

| Type | Khi nào | Payload |
|------|---------|---------|
| `action` | Tool bắt đầu chạy | `{tool, input, status:"running"}` |
| `action_result` | Tool hoàn tất | `{tool, output, status:"completed"}` |
| `text` | Chunk text từ LLM | `{content, done:false}` |
| `done` | Agent loop kết thúc | `{}` |
| `error` | Có exception | `{detail}` |

---

## 3. Tool Specifications

### BaseTool Interface

```python
class BaseTool(ABC):
    name: str
    description: str
    parameters: dict   # JSON Schema cho LLM hiểu

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult

class ToolResult:
    success: bool
    data: Any
    error: str | None = None
    metadata: dict = {}
```

`ToolRegistry.to_langchain_tools()` convert sang `StructuredTool` để LangGraph dùng.

### Tool: `web_search`
- **Input**: `query: str`, `num_results: int = 5`
- **Engine**: `duckduckgo-search` v8 (sync DDGS gọi qua `asyncio.to_thread`)
- **Output**: List of `{title, snippet, url}`. Trả `[]` nếu không có kết quả.

### Tool: `web_browser`
- **Input**: `url: str`, `action: "goto"|"get_text"|"screenshot"`
- **Engine**: Playwright Chromium headless (singleton)
- **Output**: Page text hoặc base64 PNG.

### Tool: `browser_control` (OpenClaw-style)
- **Input**: `action: "click"|"type"|"hover"|"navigate"`, `target: str` (CSS selector hoặc accessibility label)
- **Engine**: Playwright DOM/accessibility APIs
- **Output**: `{success, current_url, error?}`

### Tool: `screenshot`
- **Input**: `region: dict | None`
- **Engine**: `mss` (cross-platform)
- **Output**: Base64 PNG.

### Tool: `desktop_control` (Phase 5)
- **Input**: `action: "click"|"type"|"hotkey"`, params phụ thuộc action
- **Engine**: PyAutoGUI + screenshot verify
- **Safety**: Mọi action đi qua Safety Layer; Level 3+ cần confirm.

### Tool: `file_manager`
- **Input**: `action: "read"|"write"|"list"|"delete"`, `path: str`, `content?: str`
- **Engine**: `pathlib`, có whitelist sandbox dirs
- **Safety**: `delete`/`write` ngoài whitelist → BLOCK

### Tool: `app_launcher`
- **Input**: `app: str`
- **Engine**: `subprocess.Popen` với whitelist app names
- **Safety**: App không có trong whitelist → BLOCK

### Tool: `rag_search` (Phase 6)
- **Input**: `query: str`, `top_k: int = 5`
- **Engine**: ChromaDB PersistentClient + sentence-transformers (all-MiniLM-L6-v2)
- **Output**: `[{content, metadata, score}]` cho top-K cosine matches.
- **Lưu ý**: System prompt yêu cầu agent ưu tiên `rag_search` trước `web_search` khi câu hỏi liên quan tài liệu.

### Tool: `skill_manager` (Phase 11)
- **Input**: `action: "list"|"search"|"install"|"remove"`, `query: str`, `skill_id: str`
- **Engine**: Quản lý file .md cục bộ trong `backend/skills/` + GitHub API search để tìm skill từ remote.
- **Output**: Danh sách skills hoặc thông báo kết quả install/remove.
- **Safety**: AUTO (list/search), NOTIFY (install/remove)

### Tool: `shell_exec` (Phase 13)
- **Input**: `command: str`, `timeout: int` (default 30, max 120), `working_dir: str`
- **Engine**: `asyncio.create_subprocess_shell`; stdout và stderr được capture; output bị truncate ở 50K ký tự.
- **Safety**: CONFIRM (tất cả). BLOCK tự động nếu command chứa: `rm -rf /`, `format`, `mkfs`, fork bomb, `reg delete`, v.v.

### Tool: `clipboard` (Phase 13)
- **Input**: `action: "read"|"write"`, `content: str` (chỉ cho write)
- **Engine**: `pyperclip` chạy qua `asyncio.to_thread`
- **Safety**: AUTO (read), NOTIFY (write)

### Tool: `system_notification` (Phase 13)
- **Input**: `title: str`, `message: str`, `urgency: "low"|"normal"|"critical"`
- **Engine**: `plyer.notification.notify()` (cross-platform: Windows/macOS/Linux)
- **Safety**: NOTIFY

### Tool: `email` (Phase 14)
- **Input**: `action: "read_inbox"|"read_email"|"search"|"send"`, params phụ thuộc action
- **Engine**: `IMAP4_SSL` (đọc) + `SMTP` (gửi), gọi qua `asyncio.to_thread`
- **Config**: `IMAP_HOST/PORT/USER/PASSWORD`, `SMTP_HOST/PORT/USER/PASSWORD` trong `.env`
- **Safety**: AUTO (read/search), CONFIRM (send)

### Tool: `image_generator` (Phase 15)
- **Input**: `prompt: str`, `size: str`, `style: "vivid"|"natural"`, `save_path: str`
- **Engine**: OpenAI DALL-E 3 API qua `httpx`
- **Output**: Lưu file vào `uploads/generated/{uuid}.png`; trả về file path. Ảnh có thể serve qua `GET /api/files/generated/{filename}`.
- **Safety**: NOTIFY

### Tool: `code_runner` (Phase 15)
- **Input**: `language: "python"|"javascript"|"typescript"|"bash"|"powershell"|"godot"`, `code: str`, `timeout: int`, `working_dir: str`
- **Engine**: Ghi ra temp file, thực thi qua `asyncio.create_subprocess_exec`. Godot: `godot --headless --script` (cần `GODOT_PATH` env).
- **Output**: stdout/stderr truncate 50K ký tự. Temp files tự xoá sau 1 giờ.
- **Safety**: CONFIRM

---

## 4. Safety Layer

```python
class SafetyLevel(Enum):
    AUTO    = 1   # web_search, rag_search, screenshot, clipboard(read), skill_manager(list/search), email(read/search)
    NOTIFY  = 2   # web_browser goto, file_manager read/list, clipboard(write), system_notification, image_generator, skill_manager(install/remove)
    CONFIRM = 3   # file_manager write, desktop_control, app_launcher, shell_exec, email(send), code_runner
    BLOCK   = 4   # delete system files, rm -rf /, format, mkfs, fork bomb, reg delete, taskkill, bcdedit
```

| Safety Level | Tools |
|---|---|
| AUTO | web_search, rag_search, screenshot, clipboard(read), skill_manager(list/search), email(read/search) |
| NOTIFY | web_browser goto, file_manager read/list, clipboard(write), system_notification, image_generator, skill_manager(install/remove) |
| CONFIRM | file_manager write, desktop_control, app_launcher, shell_exec, email(send), code_runner |
| BLOCK | delete system files, `rm -rf /`, format, mkfs, fork bomb, `reg delete`, `taskkill`, `bcdedit` |

Mọi tool call đều đi qua `SafetyGuard.check(action)` trước khi execute. Hiện tại Level 3 chưa block UI confirm runtime — agent chạy nếu prompt cho phép; Safety Layer là tầng tham chiếu cho audit và phát triển tiếp.

---

## 5. LLM Provider Factory

### Module: `app/agent/brain.py::_build_llm`

```python
def _build_llm(provider: str, model: str):
    if provider == "openai":
        # ChatOpenAI; hỗ trợ base_url proxy qua OPENAI_BASE_URL env
        return ChatOpenAI(model, api_key=settings.openai_api_key, temperature=0)
    if provider == "gemini":
        # ChatGoogleGenerativeAI hoặc ChatOpenAI (proxy mode qua GEMINI_BASE_URL)
        return ChatGoogleGenerativeAI(model, google_api_key=settings.google_api_key, temperature=0)
    if provider == "claude":
        # ChatAnthropic; hỗ trợ anthropic_api_url proxy
        return ChatAnthropic(model, api_key=settings.anthropic_api_key, temperature=0)
    if provider == "groq":
        # ChatOpenAI với base_url trỏ tới Groq API
        return ChatOpenAI(model, base_url="https://api.groq.com/openai/v1", api_key=settings.groq_api_key, temperature=0)
    if provider == "sambanova":
        # ChatOpenAI với base_url trỏ tới SambaNova API
        return ChatOpenAI(model, base_url=settings.sambanova_base_url, api_key=settings.sambanova_api_key, temperature=0)
    if provider == "ollama":
        # ChatOpenAI với base_url=ollama/v1, không cần key thật
        return ChatOpenAI(model, base_url=settings.ollama_base_url+"/v1", api_key="ollama", temperature=0)
    raise ProviderNotFoundError(provider)
```

**Auto-fallback chain** (khi `DEFAULT_PROVIDER=auto`):
`groq → gemini → sambanova → openai → claude → ollama`

Bỏ qua provider nào thiếu API key. Lỗi quota runtime (429/503/"rate_limit"/"quota"/"token pool is empty") cũng trigger fallback trong `routers/agent.py`.

### Provider Matrix

| Feature | OpenAI | Gemini 2.5 | Claude | Groq | SambaNova | Ollama |
|---------|--------|-----------|--------|------|-----------|--------|
| Tool calling | Đầy đủ | Đầy đủ | Đầy đủ | Đầy đủ | Đầy đủ | Tuỳ model |
| Vision | gpt-4o | flash/pro | sonnet | Không | Không | Tuỳ model |
| Streaming | Có | Có | Có | Có | Có | Có |
| Computer Use (local) | OK | **Bị safety filter chặn** | OK | OK | OK | OK |
| RAG search | OK | OK | OK | OK | OK | OK |
| Local/Offline | Không | Không | Không | Không | Không | **Có** |
| Thinking format | str | **list[dict]** | str | str | str | str |
| Proxy support | **Có** | Có (proxy mode) | **Có** | Không | Không | Có |
| Free tier limit | - | - | - | 1000 req/day | 200 req/day | Không giới hạn |

**Model mặc định theo provider** — cấu hình qua env:
`OPENAI_MODEL`, `GEMINI_MODEL`, `CLAUDE_MODEL`, `GROQ_MODEL`, `SAMBANOVA_MODEL`

**Lưu ý Gemini 2.5**: nội dung message trả về dạng `[{"type":"text","text":"..."}, {"type":"thinking", ...}]`. Backend `run_agent`/`stream_agent` parse list, chỉ extract block `type=="text"`. Xem `backend/app/agent/brain.py`.

---

## 6. RAG Pipeline

### Upload và indexing chuẩn

```
Upload (multipart) → backend/uploads/{doc_id}.{ext}
    ↓
unstructured.partition(file)  (PDF/DOCX/PPTX/XLSX/MD/TXT)
    ↓
Chunks (semantic chunks từ unstructured)
    ↓
sentence-transformers (all-MiniLM-L6-v2) → 384-dim vector
    ↓
ChromaDB PersistentClient (backend/chroma_data/)
   collection = "jarvis_default"  (single shared collection, cosine distance)
    ↓
Metadata index: backend/uploads/documents_metadata.json
   [{doc_id, filename, uploaded_at, chunk_count, size_bytes, folder, file_ext}]
```

Query path: `rag_search(query, top_k)` → embed query → cosine top-K → trả `[{content, metadata, score}]`.

### Wikilink Pipeline (Phase 10)

```
Upload → backend/uploads/{doc_id}.{ext}
    ↓
MarkItDown (PDF/DOCX/PPTX/XLSX → Markdown)
    ↓
Wikilink Generator (LLM inject [[wikilinks]] vào nội dung)
    ↓
Lưu vào uploads/vault/{doc_id}.md
    ↓
Link Extractor (regex parse [[Target]] và [[Target|Display]])
    ↓
Graph: wikilink edges only (không dùng cosine similarity)
```

**Split LLM config**: wikilink generation dùng `WIKILINK_PROVIDER`/`WIKILINK_MODEL` (khuyến nghị Ollama local để tiết kiệm chi phí), trong khi agent chat dùng `DEFAULT_PROVIDER`. Nếu không có key cho `WIKILINK_PROVIDER`, bước wikilink bị bỏ qua và graph chỉ có orphan nodes (không có edges).

---

## 7. Skill System (Phase 11)

### Tổng quan

Skills là các file `.md` trong `backend/skills/` với frontmatter YAML chứa metadata (name, description, triggers). Chúng mở rộng khả năng của agent mà không cần thay đổi code.

### Cơ chế hoạt động

```
User message
    ↓
skill_loader.get_prompt_injection(user_message)
    ↓ so khớp keyword từ triggers trong frontmatter
Nội dung skill .md phù hợp → inject vào system prompt
    ↓
Agent có thêm context chuyên biệt cho task
```

### Cấu trúc skill file

```markdown
---
name: python-debugging
description: Hướng dẫn debug Python nâng cao
triggers: [debug, traceback, error, exception, python]
---

# Python Debugging Guide
...nội dung skill...
```

### skill_manager tool

Agent có thể tự quản lý skills qua `skill_manager` tool:
- `list` — liệt kê tất cả skills đang active
- `search` — tìm kiếm skill trên GitHub theo keyword
- `install` — tải skill về `backend/skills/`
- `remove` — xoá skill khỏi local

Skills có thể được cài từ GitHub repository hoặc tạo thủ công dưới dạng `.md` files.

---

## 8. Security Model

### API Key Management
- Lưu trong `backend/.env` (server-side only); `.env` đã có trong `.gitignore`.
- KHÔNG gửi API key qua WebSocket/API response.
- Frontend chỉ gửi `provider` name; backend lookup key từ env.

### Tool Sandbox
- Playwright: browser context riêng, tự `close()` sau session.
- File operations: whitelist directory.
- Desktop/App: Safety Layer 4 cấp.
- Shell exec: BLOCK list cho các lệnh nguy hiểm.
- Code runner: temp files tự cleanup sau 1 giờ.

### Input Validation
- Pydantic v2 schemas validate mọi request.
- `ChatRequest.messages` min_length=1.
- `temperature` clamp [0.0, 2.0]; `max_tokens` clamp [1, 128000].
- `GET /api/files/generated/{filename}`: path traversal protection — reject filename chứa `/` hay `..`.

### CORS
- Dev: cho phép `http://localhost:5173` và `http://localhost:3000`.
- Production: cấu hình qua `CORS_ORIGINS` env var.

---

## 9. Frontend Architecture

### Component tree

```
App.jsx (viewMode: 'chat' | 'graph')
├── [Chat View]
│   ├── Sidebar (doc tree: SidebarDocTree/SidebarDocNode, drag-drop upload)
│   ├── ChatArea
│   │   ├── EmptyState (centered input "What's on the agenda today?")
│   │   ├── MessageList (full-width, no bubble)
│   │   │   └── MessageBubble (markdown + inline images)
│   │   ├── ActionViewer / ActionStep (timeline tool calls)
│   │   ├── AttachmentPreview (pill badges hiển thị file đính kèm)
│   │   └── InputBar (sticky bottom) + VoiceButton + CancelButton
│   ├── SettingsPanel (modal: provider, model, test, language)
│   └── DocumentsPanel (modal: upload, list, delete)
├── [Graph View] (GraphPage.jsx — 3-panel Obsidian layout)
│   ├── GraphLeftPanel (search, doc list, detail on node click, MarkdownEditorPanel)
│   ├── GraphCanvas (react-force-graph-2d, folder-based coloring, hover highlight, filter)
│   └── ChatArea (floating overlay với suggestion chips)
└── Header (language toggle EN/VI)
```

### Hooks

- `useAgent` — REST `POST /api/agent/execute` + WebSocket `/ws/agent` fallback
- `useWebSocket` — generic WS với auto-reconnect exponential backoff
- `useVoice` — Web Speech API STT (continuous=false để tránh TTS echo loop) + SpeechSynthesis TTS
- `useSettings` — localStorage persistence cho provider/model/lang/voice
- `useAttachments` — quản lý file đính kèm ephemeral trong chat (upload, preview, clear)
- `useGraph` — fetch và quản lý state của knowledge graph
- `useDocTree` — quản lý cây thư mục tài liệu trong Sidebar

### Streaming UX

- Khi WS gửi `text` event → append vào message hiện tại (typewriter effect tự nhiên).
- Khi WS gửi `action` → push vào ActionViewer; `action_result` cập nhật kết quả.
- `done` event → mark message hoàn tất, auto-TTS nếu enabled.

---

## 10. Error Handling & Reliability (Phase 7)

### Backend
- Mọi tool wrap try/except → `ToolResult(success=False, error=...)`. Agent loop không crash.
- Provider auth thiếu → `ProviderAuthError(provider)` 400 với message rõ ràng.
- LangGraph recursion vượt limit → trả response một phần + log warning.

### Frontend
- `useAgent` retry 3 lần với exponential backoff (250ms, 500ms, 1000ms) cho lỗi network.
- Toast notification (react-bootstrap) khi backend không kết nối được — không lặp message vào chat.
- WebSocket disconnect → auto-reconnect tối đa 5 lần, sau đó hiển thị toast "Connection lost".

### Startup health checks (lifespan)
- Test ChromaDB write/delete một test document.
- Cảnh báo nếu không có API key nào.
- Cảnh báo nếu Playwright chromium chưa install.

---

## 11. Testing

| Layer | Framework | Trạng thái |
|-------|-----------|-----------|
| Backend unit | pytest + pytest-asyncio | LLM Factory, Tool Registry, Safety Layer |
| Backend integration | pytest + httpx | `/api/chat`, `/api/agent`, `/api/documents`, `/api/graph`, `/api/usage` |
| Backend RAG | pytest | embeddings, vector_store, document_parser |
| Backend Graph | pytest | wikilink extractor, cache hashing, builder edge cases (`test_graph.py`) |
| Backend Tools (Phase 13–15) | pytest | shell_exec, clipboard, email, image_generator, code_runner |
| Frontend E2E | Playwright | 4 flows: `app-loads`, `settings-panel`, `documents-panel`, `graph-panel` |

**Tổng: 148/148 tests passing.**

```bash
# Backend — run in backend/ with venv active
pytest -v                                         # full suite
pytest tests/test_graph.py -v                     # single file
pytest tests/test_agent.py::TestAgent -v          # single class
pytest tests/test_tools.py -v                     # Phase 13-15 tools
pytest --cov=app --cov-report=term-missing        # coverage report

# Frontend — backend MUST already be running on :8000
cd frontend && npm run test:e2e
cd frontend && npm run test:e2e:ui                # UI mode
```

---

## 12. SQLite persistence layer (Phase 16)

Documents, wikilinks, email accounts, cached email messages, the user profile, and job listings all live in a single SQLite file (`./jarvis.db` by default).

- **Engine** — `app.db.connection.engine` built with `sqlalchemy[asyncio] + aiosqlite`. Every new connection runs `PRAGMA foreign_keys=ON` and `PRAGMA journal_mode=WAL`.
- **Schema** — `app.db.models.Base.metadata` holds 7 ORM tables (`documents`, `wikilinks`, `email_accounts`, `email_messages`, `user_profile`, `jobs`, `saved_job_searches`) plus an FTS5 virtual table `email_messages_fts` mirroring `subject/from_addr/body` through insert/delete/update triggers.
- **Bootstrap** — `init_db()` runs `create_all` + the FTS5 DDL on startup. `migrate_json_if_needed()` imports any legacy `uploads/documents_metadata.json` exactly once (documents first, wikilinks resolved via filename matching), then renames the file to `.migrated`.
- **Write path** — the documents router persists via `app.db.services.documents` (`create_document`, `update_document_fields`, `replace_outgoing_wikilinks`). The wikilink resolver lives here so the graph builder only has to JOIN.
- **Agent access** — the `doc_query` tool (`app/tools/doc_query.py`) exposes `find_by_wikilink`, `find_backlinks`, `list_by_folder`, `list_all`, `get_metadata`, and `read_doc` so the agent can scan metadata without dumping the full JSON index into every prompt.

## 13. Multi-Gmail + FTS5 search cache (Phase 17)

- **Encrypted credentials** — `app.services.secrets` wraps `cryptography.Fernet`. `settings.jarvis_secret_key` is auto-generated on first boot and appended to `backend/.env` with a warning log. Passwords are stored in the `email_accounts` table as Fernet tokens and only decrypted inside `EmailClient`.
- **Account CRUD** — `app.db.services.email_accounts` + `app.routers.email_accounts` expose `GET/POST/PATCH/DELETE /api/email-accounts` and `POST /api/email-accounts/{id}/test` (live IMAP login check). Exactly one row carries `is_default=True`; `update_account(is_default=True)` demotes the previous default.
- **Per-account client** — `app.services.email_client.EmailClient(credentials)` replaces the old `settings.imap_*` singleton. The tool-facing layer (`email` tool) accepts an `account=<label|id>` parameter; omit it to use the default.
- **New search actions** — `search_by_date` (IMAP `SINCE` / `BEFORE`, YYYY-MM-DD), `search_by_sender`, `search_important` (`FLAGGED`), and `search_cached` (FTS5 over the locally-synced `email_messages` table).
- **Background sync** — `app.services.email_sync.start_scheduler()` runs an APScheduler job every `email_sync_interval_minutes` (default 5) that pulls the most recent UIDs from each enabled account and upserts rows into `email_messages`. FTS5 triggers keep the virtual table in sync automatically.

## 14. User Profile + Job Search (Phase 18)

- **Profile** — singleton row in `user_profile`. `POST /api/profile/upload` parses a CV via `DocumentParser` → `app.services.cv_extractor.extract_profile_fields` (LLM JSON) → upserts skills/titles/locations/remote preference. `GET/PUT /api/profile` lets the UI edit any field manually.
- **Job sources** — 6 adapters under `app.services.job_sources/`: `duckduckgo` (via `ddgs`), `remoteok` (public JSON), `weworkremotely` (RSS), plus best-effort HTML scrapers for `topcv`, `itviec`, `vietnamworks`. Every adapter catches every exception and returns `[]` so one flaky site never breaks the pipeline.
- **Matching** — `app.services.jobs_matcher.score_job(job, profile)` returns a 0..1 Jaccard overlap of profile skills/titles against job title+description, plus small bonuses when the job location or remote flag matches the user's preferences.
- **Refresh flow** — `POST /api/jobs/refresh` runs every enabled `SavedJobSearch` against every source, dedupes by `(source, url)`, upserts into `jobs` with a fresh match_score, and purges the oldest non-saved rows when the table exceeds 500 entries. `refresh_from_profile_defaults` runs the same flow when no saved searches exist, using the profile's `preferred_titles` × `preferred_locations` grid.
- **Agent access** — the `job_search` tool exposes `list_tracked`, `search` (one-off cross-source), `refresh`, and `save`/`unsave`.
- **Scheduling** — APScheduler fires `jobs_refresh` every `jobs_refresh_interval_minutes` (default 1440 = daily).
