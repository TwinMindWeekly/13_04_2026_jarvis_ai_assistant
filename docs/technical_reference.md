# JARVIS AI Assistant - Technical Reference

> Tài liệu kỹ thuật chi tiết về kiến trúc, API, và luồng dữ liệu.
> Cập nhật lần cuối: 15/04/2026

---

## 1. Kiến trúc tổng quan

### Mô hình kiến trúc: Agent-based Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT (React)                        │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ ChatArea  │  │ ActionViewer │  │ VoiceInterface (Phase4)│ │
│  └────┬─────┘  └──────┬───────┘  └───────────┬────────────┘ │
│       │               │                      │               │
│       └───────────────┼──────────────────────┘               │
│                       │                                      │
│              ┌────────▼────────┐                             │
│              │  WebSocket Hub   │                             │
│              └────────┬────────┘                             │
└───────────────────────┼─────────────────────────────────────┘
                        │
              ┌─────────▼─────────┐
              │   FastAPI Server   │
              │   (Port 8000)      │
              ├────────────────────┤
              │ Routers:           │
              │ ├── /api/chat      │
              │ ├── /api/agent     │
              │ ├── /api/providers │
              │ └── /ws/agent      │
              ├────────────────────┤
              │ Agent Brain        │
              │ (LangGraph ReAct)  │
              │ ┌────────────────┐ │
              │ │ Think → Act →  │ │
              │ │ Observe → Loop │ │
              │ └────────────────┘ │
              ├────────────────────┤
              │ Tool Registry      │
              │ ├── web_search     │
              │ ├── web_browser    │
              │ ├── screenshot     │
              │ ├── computer_use   │
              │ ├── file_manager   │
              │ └── rag_search     │
              ├────────────────────┤
              │ LLM Factory        │
              │ ├── OpenAI         │
              │ ├── Gemini         │
              │ ├── Claude         │
              │ └── Ollama         │
              └────────────────────┘
```

### Luồng xử lý chính

```
User Input (text/voice)
    │
    ▼
[1] API Gateway (FastAPI)
    │ - Validate input
    │ - Route to agent
    ▼
[2] Agent Brain (LangGraph)
    │ - Analyze user intent
    │ - Plan actions
    ▼
[3] Tool Selection
    │ - LLM decides which tool(s) to call
    │ - May call multiple tools sequentially
    ▼
[4] Tool Execution
    │ - Execute selected tool
    │ - Return observation to agent
    ▼
[5] Agent Review
    │ - Evaluate tool result
    │ - Decide: respond or call more tools?
    ▼
[6] Response Generation
    │ - Synthesize final answer
    │ - Stream to client via WebSocket
    ▼
User Output (text/voice + action viewer)
```

---

## 2. API Reference

### REST Endpoints

#### `POST /api/chat`
Chat đơn giản không qua agent (direct LLM call).

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "Xin chào"}
  ],
  "provider": "openai",
  "model": "gpt-4o",
  "stream": true
}
```

**Response (SSE):**
```
data: {"content": "Xin", "done": false}
data: {"content": " chào", "done": false}
data: {"content": "!", "done": true}
```

#### `POST /api/agent/execute`
Gửi yêu cầu cho agent xử lý (có thể gọi tools).

**Request:**
```json
{
  "message": "Tìm thời tiết Hà Nội hôm nay",
  "provider": "openai",
  "model": "gpt-4o",
  "conversation_id": "uuid-here"
}
```

**Response:**
```json
{
  "conversation_id": "uuid-here",
  "actions": [
    {
      "step": 1,
      "tool": "web_search",
      "input": {"query": "thời tiết Hà Nội hôm nay"},
      "output": {"results": [...]},
      "duration_ms": 1200
    }
  ],
  "response": "Thời tiết Hà Nội hôm nay...",
  "tokens_used": 850
}
```

#### `GET /api/providers`
Liệt kê LLM providers khả dụng.

#### `POST /api/providers/test`
Test kết nối đến một provider.

### WebSocket Endpoints

#### `ws://localhost:8000/ws/agent`
Kênh real-time cho agent execution.

**Message Types (Server → Client):**
| Type | Mô tả |
|------|--------|
| `action` | Agent bắt đầu gọi tool |
| `action_result` | Tool trả về kết quả |
| `text` | Streaming text response |
| `voice` | Audio response (Phase 4) |
| `error` | Lỗi xảy ra |
| `done` | Agent hoàn thành |

---

## 3. Tool Specifications

### BaseTool Interface

```python
class BaseTool(ABC):
    name: str
    description: str
    parameters: dict  # JSON Schema

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult

class ToolResult:
    success: bool
    data: Any           # Kết quả (text, dict, base64 image, etc.)
    error: str | None   # Thông báo lỗi nếu có
    metadata: dict      # Thông tin bổ sung (duration, source URL, etc.)
```

### Tool: web_search
- **Input**: `query: str`, `num_results: int = 5`
- **Output**: List of `{title, snippet, url}`
- **Providers**: Google Custom Search API → Bing → DuckDuckGo (fallback chain)

### Tool: web_browser
- **Input**: `url: str`, `action: str` (goto/get_text/screenshot/click/fill)
- **Output**: Page content (text) hoặc screenshot (base64)
- **Engine**: Playwright (headless Chromium)
- **Timeout**: 30 seconds per action

### Tool: screenshot
- **Input**: `region: dict | None` (x, y, width, height)
- **Output**: Screenshot (base64 PNG)
- **Engine**: mss (cross-platform)

### Tool: computer_use (Phase 5)
- **Input**: `action: str` (click/type/scroll/hotkey), `params: dict`
- **Output**: Screenshot after action
- **Safety**: Requires user confirmation for Level 3+ actions

### Tool: rag_search (Phase 6)
- **Input**: `query: str`, `collection: str`
- **Output**: List of `{content, metadata, similarity_score}`
- **Engine**: ChromaDB + sentence-transformers

---

## 4. LLM Provider Factory

### Interface

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]
```

### Provider Matrix

| Feature | OpenAI | Gemini | Claude | Ollama |
|---------|--------|--------|--------|--------|
| Function Calling | Yes | Yes | Yes (tool_use) | Yes (partial) |
| Vision | Yes (GPT-4o) | Yes (1.5/2.0) | Yes (Sonnet) | Model-dependent |
| Streaming | Yes | Yes | Yes | Yes |
| Computer Use | No | No | Yes | No |
| Local/Offline | No | No | No | Yes |

---

## 5. Security Model

### API Key Management
- Lưu trong `.env` file (server-side only)
- KHÔNG BAO GIỜ gửi API key qua WebSocket/API response
- Frontend chỉ gửi provider name, backend tự lấy key từ env

### Tool Execution Sandbox
- Playwright browser: riêng browser context, tự close sau session
- File operations: giới hạn trong thư mục cho phép (whitelist)
- Computer use: Safety Layer 4 cấp (auto/notify/confirm/block)

### Input Sanitization
- Validate mọi input qua Pydantic schemas
- Giới hạn message length (max 10,000 chars)
- Rate limiting: 60 requests/minute per IP
