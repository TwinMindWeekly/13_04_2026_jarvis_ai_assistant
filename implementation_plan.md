# JARVIS AI Assistant - Implementation Plan

> Lộ trình kỹ thuật chi tiết cho từng Phase.
> Cập nhật lần cuối: 15/04/2026

---

## Tổng quan kiến trúc

Hệ thống theo mô hình **Agent-based Architecture** với 4 tầng chính:

```
[UI Layer] → [API Layer] → [Agent Layer] → [Tool Layer]
```

- **UI Layer**: React 19 + WebSocket + Web Speech API
- **API Layer**: FastAPI (REST + WebSocket)
- **Agent Layer**: LangGraph (ReAct agent loop: Think → Act → Observe)
- **Tool Layer**: Playwright, Search API, PyAutoGUI, ChromaDB

---

## Phase 1: Nền tảng Backend & LLM Provider Factory

### Mục tiêu
Xây dựng backend FastAPI có khả năng giao tiếp với nhiều LLM provider thông qua Factory Pattern.

### Cấu trúc thư mục tạo mới
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   └── exceptions.py        # Custom exception handlers
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py           # Pydantic request/response schemas
│   ├── services/
│   │   ├── __init__.py
│   │   └── llm_factory.py       # Multi-provider LLM Factory
│   └── routers/
│       ├── __init__.py
│       └── chat.py              # /api/chat endpoint
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_llm_factory.py
├── requirements.txt
├── .env.example
└── pyproject.toml
```

### Chi tiết kỹ thuật

**LLM Factory Pattern:**
```python
# Mỗi provider implement interface chung
class BaseLLMProvider(ABC):
    async def chat(self, messages, tools=None, **kwargs) -> LLMResponse
    async def chat_stream(self, messages, tools=None, **kwargs) -> AsyncIterator[str]

# Factory chọn provider theo config
class LLMFactory:
    @staticmethod
    def create(provider: str, model: str, api_key: str) -> BaseLLMProvider
```

**Providers triển khai:**
- `OpenAIProvider` - sử dụng `openai` SDK, hỗ trợ function calling
- `GeminiProvider` - sử dụng `google-generativeai` SDK
- `ClaudeProvider` - sử dụng `anthropic` SDK, hỗ trợ tool use
- `OllamaProvider` - gọi Ollama local API (http://localhost:11434)

**API Endpoint:**
- `POST /api/chat` - Nhận message, trả về response (streaming via SSE)
- `GET /api/providers` - Liệt kê providers khả dụng
- `POST /api/providers/test` - Test kết nối provider

**Thư viện:**
- `fastapi>=0.115.0`
- `uvicorn>=0.34.0`
- `pydantic>=2.10.0`
- `pydantic-settings>=2.7.0`
- `openai>=1.60.0`
- `google-generativeai>=0.8.0`
- `anthropic>=0.42.0`
- `ollama>=0.4.0`
- `python-dotenv>=1.0.0`
- `pytest>=8.0.0`
- `pytest-asyncio>=0.24.0`
- `httpx>=0.28.0` (test client)

---

## Phase 2: Tool Registry & Agent Brain

### Mục tiêu
Xây dựng hệ thống tool có thể mở rộng và Agent Brain có khả năng tự suy luận để chọn tool phù hợp.

### File tạo mới
```
backend/app/
├── tools/
│   ├── __init__.py
│   ├── base.py                  # BaseTool interface
│   ├── registry.py              # ToolRegistry (đăng ký & quản lý tools)
│   ├── web_search.py            # Google/Bing search
│   ├── web_browser.py           # Playwright browser automation
│   └── screenshot.py            # Desktop screenshot
├── agent/
│   ├── __init__.py
│   ├── brain.py                 # LangGraph agent (ReAct loop)
│   ├── prompts.py               # System prompts cho agent
│   └── state.py                 # Agent state definition
└── routers/
    └── agent.py                 # /api/agent/* endpoints
```

### Chi tiết kỹ thuật

**Tool Interface:**
```python
class BaseTool(ABC):
    name: str                     # Tên tool (VD: "web_search")
    description: str              # Mô tả cho LLM hiểu khi nào dùng
    parameters: dict              # JSON Schema cho input params

    async def execute(self, **kwargs) -> ToolResult
```

**Tool Registry:**
```python
class ToolRegistry:
    def register(self, tool: BaseTool)
    def get_tool(self, name: str) -> BaseTool
    def get_all_schemas(self) -> list[dict]   # Trả về tool schemas cho LLM
```

**Agent Brain (LangGraph ReAct):**
```
START → [Think] → [Decide: call tool or respond?]
              ↓ call tool              ↓ respond
         [Execute Tool]          [Return Answer]
              ↓
         [Observe Result] → [Think] (loop lại)
```

- Sử dụng LangGraph `StateGraph` với các node: `think`, `act`, `observe`
- Giới hạn tối đa 10 bước tool call để tránh loop vô hạn
- Mỗi bước ghi log vào `action_history` để frontend hiển thị

**Web Search Tool:**
- Sử dụng Google Custom Search API hoặc Bing Search API
- Fallback: DuckDuckGo (không cần API key)
- Trả về: title, snippet, URL cho top 5 kết quả

**Web Browser Tool:**
- Sử dụng Playwright (headless Chromium)
- Actions: `goto(url)`, `get_text()`, `screenshot()`, `click(selector)`, `fill(selector, text)`
- Trả về: page content (text) + screenshot (base64)
- Sandbox: Chạy trong browser context riêng, tự dọn sau mỗi session

**Thư viện bổ sung:**
- `langgraph>=0.2.0`
- `langchain-core>=0.3.0`
- `playwright>=1.49.0`
- `duckduckgo-search>=7.0.0` (fallback search)
- `Pillow>=11.0.0`
- `mss>=9.0.0` (screenshot)

---

## Phase 3: Frontend Chat & Action Viewer

### Mục tiêu
Giao diện người dùng hiện đại, hiển thị cả chat và hành động agent real-time.

### File tạo mới
```
frontend/
├── src/
│   ├── App.jsx
│   ├── main.jsx
│   ├── main.css                      # Global styles, glassmorphism
│   ├── components/
│   │   ├── ChatArea.jsx              # Khu vực chat chính
│   │   ├── MessageBubble.jsx         # Tin nhắn (text, markdown, image)
│   │   ├── ActionViewer.jsx          # Hiển thị tool execution real-time
│   │   ├── ActionStep.jsx            # Từng bước agent (tool name, input, output)
│   │   ├── Sidebar.jsx               # Navigation, conversation history
│   │   ├── SettingsPanel.jsx         # Cấu hình provider, model, API key
│   │   └── VoiceButton.jsx           # Nút microphone (Phase 4)
│   ├── hooks/
│   │   ├── useWebSocket.js           # WebSocket connection manager
│   │   ├── useAgent.js               # Agent API calls
│   │   └── useSettings.js            # Settings state (localStorage)
│   ├── services/
│   │   └── api.js                    # Axios HTTP client
│   ├── i18n/
│   │   ├── index.js
│   │   ├── en.json
│   │   └── vi.json
│   └── utils/
│       └── markdown.js               # Markdown renderer config
├── index.html
├── package.json
├── vite.config.js
└── tailwind.config.js
```

### Chi tiết kỹ thuật

**ActionViewer** - Điểm khác biệt so với chatbot thông thường:
- Hiển thị từng bước agent thực hiện dưới dạng timeline
- Mỗi step: icon tool → input params → loading → kết quả (text/screenshot)
- Collapsible: mặc định thu gọn, click để xem chi tiết
- Real-time update qua WebSocket

**WebSocket Protocol:**
```json
// Server → Client: Agent action update
{
  "type": "action",
  "step": 1,
  "tool": "web_search",
  "input": {"query": "thời tiết Hà Nội"},
  "status": "running"
}

// Server → Client: Action result
{
  "type": "action_result",
  "step": 1,
  "output": {"results": [...]},
  "status": "completed"
}

// Server → Client: Text response (streaming)
{
  "type": "text",
  "content": "Theo kết quả tìm kiếm...",
  "done": false
}
```

**Thư viện Frontend:**
- `react@19`, `react-dom@19`
- `vite@6+`
- `axios` (HTTP client)
- `i18next`, `react-i18next` (i18n)
- `react-markdown`, `remark-gfm` (markdown rendering)
- `tailwindcss@4` (styling)
- `lucide-react` (icons)
- `framer-motion` (animations)

---

## Phase 4: Voice Interface

### Mục tiêu
Thêm khả năng giao tiếp bằng giọng nói, biến JARVIS thành trợ lý voice-first.

### Chi tiết kỹ thuật

**Speech-to-Text (Frontend):**
- Web Speech API (`SpeechRecognition`) - miễn phí, chạy trên browser
- Fallback: Whisper API (OpenAI) cho accuracy cao hơn
- Continuous listening mode với voice activity detection

**Text-to-Speech (Frontend + Backend):**
- Option 1: Browser native `SpeechSynthesis` (miễn phí, offline)
- Option 2: OpenAI TTS API (giọng tự nhiên hơn)
- Option 3: Google Cloud TTS (đa ngôn ngữ)
- Người dùng chọn engine trong Settings

**Voice UI:**
- Nút microphone với animation sóng âm khi đang nghe
- Auto-detect khi người dùng ngừng nói → gửi transcript
- TTS phát khi nhận response → tự tắt mic khi đang phát

**WebSocket Voice Channel (Nâng cao):**
- Binary WebSocket cho audio streaming (học từ PersonaPlex pattern)
- Opus encoding/decoding cho bandwidth thấp
- Cho phép interrupt (người dùng nói giữa chừng → agent dừng TTS)

---

## Phase 5: Computer Use & Advanced Actions

### Mục tiêu
Nâng cấp agent có thể thao tác trực tiếp trên máy tính người dùng.

### Chi tiết kỹ thuật

**Computer Use Tool:**
- Primary: Claude Computer Use API (Claude nhìn screenshot → quyết định click/type)
- Fallback: PyAutoGUI (click, type, hotkey dựa trên tọa độ)
- Chạy trong sandbox với permission system

**Safety Layer (BẮT BUỘC):**
```python
class SafetyGuard:
    DANGEROUS_ACTIONS = ["delete", "format", "rm -rf", "shutdown"]

    async def check(self, action: ToolAction) -> SafetyResult:
        # Level 1: Auto-approve (web search, read file)
        # Level 2: Notify (open app, navigate web)
        # Level 3: Require confirmation (write file, install software)
        # Level 4: Block (delete system files, format disk)
```

**Live Screen Viewer:**
- Backend liên tục chụp screenshot khi agent đang thao tác
- Stream qua WebSocket (MJPEG hoặc base64 frames)
- Frontend hiển thị real-time + overlay highlight vùng agent đang tương tác

---

## Phase 6: RAG Integration

### Mục tiêu
Tận dụng kiến trúc RAG từ dự án `06_04_2026_multimodal_rag_ai`.

### Chi tiết kỹ thuật

- Tái sử dụng module: `embeddings.py`, `vector_store.py` từ dự án RAG
- ChromaDB cho vector storage (per-conversation collection)
- Agent tự quyết: nếu câu hỏi liên quan tài liệu đã upload → dùng RAG, ngược lại → web search
- Citation metadata: filename, page number, chunk text

---

## Phase 7: Testing & Polish

### Checklist
- [ ] Unit Test coverage >= 80% cho backend services
- [ ] Integration Test cho agent workflow (mock LLM + real tools)
- [ ] E2E Test cho frontend flows (Playwright)
- [ ] Security: API key encryption at rest, input sanitization, tool sandboxing
- [ ] Performance: streaming latency < 500ms TTFB, tool execution timeout 30s
- [ ] Error handling: retry logic, graceful degradation, user-friendly error messages
- [ ] Documentation: README, API docs, architecture diagrams cập nhật

---

## Ước lượng thư viện chính

| Package | Version | Phase |
|---------|---------|-------|
| fastapi | >=0.115.0 | 1 |
| langchain-core | >=0.3.0 | 2 |
| langgraph | >=0.2.0 | 2 |
| playwright | >=1.49.0 | 2 |
| openai | >=1.60.0 | 1 |
| anthropic | >=0.42.0 | 1 |
| google-generativeai | >=0.8.0 | 1 |
| chromadb | >=0.5.0 | 6 |
| react | 19 | 3 |
| vite | >=6.0.0 | 3 |
| tailwindcss | >=4.0.0 | 3 |

---

## Nguyên tắc thiết kế xuyên suốt

1. **Modular**: Mỗi tool là 1 file, mỗi provider là 1 class, dễ thêm/bớt
2. **Async-first**: Toàn bộ backend dùng async/await
3. **Stream-first**: Mọi response đều hỗ trợ streaming (SSE hoặc WebSocket)
4. **Safety-first**: Mọi hành động nguy hiểm phải qua Safety Layer
5. **Provider-agnostic**: Đổi LLM provider không ảnh hưởng logic agent
