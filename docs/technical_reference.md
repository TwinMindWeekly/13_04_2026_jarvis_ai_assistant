# JARVIS AI Assistant - Technical Reference

> Tài liệu kỹ thuật chi tiết về kiến trúc, API, và luồng dữ liệu.
> Cập nhật lần cuối: 15/04/2026 (Phase 7)

---

## 1. Kiến trúc tổng quan

### Mô hình kiến trúc: Agent-based Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT (React 19 + Vite 8)                │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ ChatArea │  │ ActionViewer │  │ DocumentsPanel (RAG) │   │
│  │ Sidebar  │  │ SettingsPanel│  │ VoiceButton          │   │
│  └────┬─────┘  └──────┬───────┘  └──────────┬───────────┘   │
│       └────────────────┴─────────────────────┘               │
│                  React hooks: useAgent, useWebSocket,        │
│                              useVoice, useSettings           │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST + SSE + WebSocket
              ┌────────▼────────────────┐
              │  FastAPI Server (8000)  │
              ├─────────────────────────┤
              │ Routers:                │
              │ ├── /api/chat           │  (direct LLM, SSE stream)
              │ ├── /api/agent/execute  │  (REST, ReAct loop)
              │ ├── /ws/agent           │  (WebSocket streaming)
              │ ├── /api/providers      │  (list / test)
              │ └── /api/documents      │  (RAG upload/list/delete)
              ├─────────────────────────┤
              │ Agent Brain             │
              │ LangGraph create_react_ │
              │ agent (Think→Act→Loop)  │
              ├─────────────────────────┤
              │ Tool Registry (8 tools) │
              │ ├── web_search          │
              │ ├── web_browser         │
              │ ├── browser_control     │
              │ ├── screenshot          │
              │ ├── desktop_control     │
              │ ├── file_manager        │
              │ ├── app_launcher        │
              │ └── rag_search          │
              ├─────────────────────────┤
              │ Safety Layer            │
              │ AUTO/NOTIFY/CONFIRM/    │
              │ BLOCK                   │
              ├─────────────────────────┤
              │ LLM Factory             │
              │ ├── OpenAI              │
              │ ├── Gemini (2.5)        │
              │ ├── Claude              │
              │ └── Ollama              │
              └─────────────────────────┘
```

### Luồng xử lý chính

```
User input (text or voice via SpeechRecognition)
    │
    ▼
[1] /api/agent/execute (POST) hoặc /ws/agent (WebSocket)
    │ Validate qua Pydantic AgentRequest
    ▼
[2] create_agent_brain(provider, model, tools)
    │ → LangGraph CompiledStateGraph với system prompt
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
Xoá document khỏi vector store + filesystem + metadata.

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

---

## 4. Safety Layer

```python
class SafetyLevel(Enum):
    AUTO    = 1   # web_search, rag_search, screenshot, get_text
    NOTIFY  = 2   # web_browser goto, file_manager read/list
    CONFIRM = 3   # file_manager write, desktop_control, app_launcher
    BLOCK   = 4   # delete system files, format, rm -rf, shutdown
```

Mọi tool call đều đi qua `SafetyGuard.check(action)` trước khi execute. Hiện tại Level 3 chưa block UI confirm runtime — agent chạy nếu prompt cho phép, dependencies trên Safety Layer là layer tham khảo cho audit.

---

## 5. LLM Provider Factory

### Module: `app/agent/brain.py::_build_llm`

```python
def _build_llm(provider: str, model: str):
    if provider == "openai":   return ChatOpenAI(model, api_key=settings.openai_api_key, temperature=0)
    if provider == "gemini":   return ChatGoogleGenerativeAI(model, google_api_key=settings.google_api_key, temperature=0)
    if provider == "claude":   return ChatAnthropic(model, api_key=settings.anthropic_api_key, temperature=0)
    if provider == "ollama":   return ChatOpenAI(model, base_url=settings.ollama_base_url+"/v1", api_key="ollama", temperature=0)
    raise ProviderNotFoundError(provider)
```

### Provider Matrix

| Feature | OpenAI | Gemini 2.5 | Claude | Ollama |
|---------|--------|-----------|--------|--------|
| Function/Tool calling | Đầy đủ | Đầy đủ | Đầy đủ | Tuỳ model |
| Vision | gpt-4o | flash/pro | sonnet | Tuỳ model |
| Streaming | Có | Có | Có | Có |
| Computer Use (local) | OK qua tools | **Bị safety filter chặn** | OK qua tools | OK qua tools |
| RAG search | OK | OK | OK | OK |
| Local/Offline | Không | Không | Không | **Có** |
| Thinking format | str | **list[dict]** (cần parse) | str | str |

**Lưu ý Gemini 2.5**: nội dung message trả về dạng `[{"type":"text","text":"..."}, {"type":"thinking", ...}]`. Backend `run_agent`/`stream_agent` parse list, chỉ extract block `type=="text"`. Xem `backend/app/agent/brain.py`.

---

## 6. RAG Pipeline

```
Upload (multipart) → backend/uploads/{doc_id}.{ext}
    ↓
unstructured.partition(file)  (PDF/DOCX/PPTX/XLSX/MD/TXT)
    ↓
Chunks (≈ semantic chunks từ unstructured)
    ↓
sentence-transformers (all-MiniLM-L6-v2) → 384-dim vector
    ↓
ChromaDB PersistentClient (backend/chroma_data/)
   collection = "documents"  (single shared collection)
    ↓
Metadata index: backend/uploads/_index.json
   {doc_id, filename, uploaded_at, chunk_count}
```

Query path: `rag_search(query, top_k)` → embed query → cosine top-K → trả `[{content, metadata, score}]`.

---

## 7. Security Model

### API Key Management
- Lưu trong `backend/.env` (server-side only); `.env` đã có trong `.gitignore`.
- KHÔNG gửi API key qua WebSocket/API response.
- Frontend chỉ gửi `provider` name; backend lookup key từ env.

### Tool Sandbox
- Playwright: browser context riêng, tự `close()` sau session.
- File operations: whitelist directory.
- Desktop/App: Safety Layer 4 cấp.

### Input Validation
- Pydantic v2 schemas validate mọi request.
- `ChatRequest.messages` min_length=1.
- `temperature` clamp [0.0, 2.0]; `max_tokens` clamp [1, 128000].

### CORS
- Dev: cho phép `http://localhost:5173`.
- Production: cấu hình qua `CORS_ORIGINS` env var.

---

## 8. Frontend Architecture

### Component tree

```
App.jsx
├── Sidebar (conversation list, new chat, documents button)
├── ChatArea
│   ├── EmptyState (centered input "What's on the agenda today?")
│   ├── MessageList (full-width, no bubble)
│   │   └── MessageBubble (markdown + ActionViewer collapsible)
│   ├── ActionViewer / ActionStep (timeline tool calls)
│   └── InputBar (sticky bottom, max-w 768px) + VoiceButton
├── SettingsPanel (modal: provider, model, test, language)
└── DocumentsPanel (modal: upload, list, delete)
```

### Hooks

- `useAgent` — REST `POST /api/agent/execute` + WebSocket `/ws/agent` fallback
- `useWebSocket` — generic WS với auto-reconnect exponential backoff
- `useVoice` — Web Speech API STT (continuous=false để tránh TTS echo loop) + SpeechSynthesis TTS
- `useSettings` — localStorage persistence cho provider/model/lang/voice

### Streaming UX

- Khi WS gửi `text` event → append vào message hiện tại (typewriter effect tự nhiên).
- Khi WS gửi `action` → push vào ActionViewer; `action_result` cập nhật kết quả.
- `done` event → mark message hoàn tất, auto-TTS nếu enabled.

---

## 9. Error Handling & Reliability (Phase 7)

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

## 10. Testing

| Layer | Framework | Coverage |
|-------|-----------|----------|
| Backend unit | pytest + pytest-asyncio | LLM Factory, Tool Registry, Safety Layer (127/127 passed cuối Phase 6) |
| Backend integration | pytest + httpx | /api/chat, /api/agent endpoints |
| Backend RAG | pytest | embeddings, vector_store, document_parser |
| Frontend E2E | Playwright (Phase 7) | 2-3 critical flows: chat, settings, documents |

```bash
cd backend && pytest -v
cd frontend && npx playwright test
```
