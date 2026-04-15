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

---

## Phase 9: Graph View Redesign — Obsidian 3-Panel Layout + AI Chat

### Mục tiêu

Chuyển Knowledge Graph từ modal popup → **full-page 3-panel layout** giống Obsidian Graph View:
- **Left panel** (~280px): Search + document list + document detail khi click node
- **Center**: Graph canvas full-screen nền đen, giữ ForceGraph2D
- **Right panel** (~360px): AI chat sidebar — user hỏi → agent dùng rag_search → hiện kết quả + highlight related nodes trên graph

Bỏ: threshold slider, rebuild button (UX noise, user không cần tuỳ chỉnh).
Giữ: search filter, zoom-to-fit (floating button), graph legend, drag/zoom/pan/hover.

### Reference UI

Tham chiếu Obsidian Graph View (ảnh user cung cấp):
- Sidebar trái: search box + kết quả với keyword highlight (vàng), preview text 2-3 dòng
- Giữa: graph canvas nền đen với hàng ngàn node trắng, cluster tự nhiên
- Phía dưới sidebar: folder/tag grouping

Thêm khác biệt so với Obsidian: sidebar phải là **AI chat** (JARVIS agent) thay vì file editor.

### Layout chi tiết

```
┌─────────────────────────────────────────────────────────────────────┐
│  ← Back   🔍 Search docs          📊 Graph view              ⚙️    │
├──────────────┬────────────────────────────────┬─────────────────────┤
│  LEFT PANEL  │     CENTER: GRAPH CANVAS       │  RIGHT PANEL        │
│  280px       │     flex: 1                    │  360px              │
│              │     bg: #0f1014                │                     │
│  ┌─────────┐ │                                │  AI Chat            │
│  │🔍 Search│ │        ●  ●     ●              │  ────────────       │
│  └─────────┘ │          ●  ●  ●               │  [User]: tìm tài   │
│              │       ●    ●    ●              │  liệu về API       │
│  DOCUMENTS   │        ●  ●       ●            │                     │
│  ──────────  │             ●  ●               │  [AI]: Tìm thấy    │
│  📄 API.docx │         ●     ●                │  2 tài liệu liên   │
│    49 chunks │                                │  quan:              │
│  📄 Plan.md  │                                │  • API.docx (85%)   │
│    12 chunks │                                │  • Plan.md (72%)    │
│              │                                │  [click to focus]   │
│  ──────────  │           [Fit]                │                     │
│  SELECTED    │                                │  ┌───────────────┐  │
│  (khi click) │                                │  │ Ask JARVIS... │  │
│  📄 API.docx │                                │  └───────────────┘  │
│  Folder: /   │                                │                     │
│  Chunks: 49  │                                │                     │
│  Size: 19 KB │                                │                     │
│  Neighbors:  │                                │                     │
│  - Plan.md   │                                │                     │
│    72%       │                                │                     │
├──────────────┴────────────────────────────────┴─────────────────────┤
│  Status bar: 5 docs · 12 links · click node to see details         │
└─────────────────────────────────────────────────────────────────────┘
```

### Phân rã kỹ thuật

#### Step 1: App.jsx — Graph mode thay thế ChatArea (không còn modal)

**File sửa**: `frontend/src/App.jsx`

Thay đổi:
- Thêm state `viewMode`: `'chat'` | `'graph'`
- Khi `viewMode === 'graph'` → render `<GraphPage />` thay vì `<ChatArea />`
- Sidebar button "Knowledge Graph" → `setViewMode('graph')` thay vì `setGraphOpen(true)`
- GraphPage có nút "← Back" → `setViewMode('chat')`
- Bỏ `<GraphPanel isOpen={graphOpen}>` modal cũ

```jsx
// App.jsx pseudo-code
const [viewMode, setViewMode] = useState('chat')

return (
  <div className="d-flex" style={{ height: '100vh' }}>
    <Sidebar onOpenGraph={() => setViewMode('graph')} ... />
    {viewMode === 'chat' ? (
      <main className="chat-main"> ... <ChatArea /> ... </main>
    ) : (
      <GraphPage
        onBack={() => setViewMode('chat')}
        settings={settings}
      />
    )}
  </div>
)
```

#### Step 2: GraphPage.jsx (mới) — Container 3 panel

**File tạo mới**: `frontend/src/components/GraphPage.jsx`

Trách nhiệm:
- Flex container 3 cột: `<GraphLeftPanel>` + `<GraphCanvas>` + `<GraphChatPanel>`
- Header bar: nút Back, tiêu đề "Graph view", search box (delegate xuống left panel)
- Status bar: "N docs · M links"
- Quản lý state chung: `selectedNode`, `highlightedNodes` (từ AI chat result)
- Truyền `useGraph` data xuống 3 panel qua props

```jsx
export default function GraphPage({ onBack, settings }) {
  const { data, loading, error } = useGraph({ enabled: true })
  const [selected, setSelected] = useState(null)
  const [highlighted, setHighlighted] = useState([]) // doc IDs from AI chat

  return (
    <div className="graph-page">
      <div className="graph-page-header"> ... </div>
      <div className="graph-page-body">
        <GraphLeftPanel
          nodes={data.nodes}
          links={data.links}
          selected={selected}
          onSelectNode={setSelected}
        />
        <GraphCanvas
          data={data}
          selected={selected}
          highlighted={highlighted}
          onSelectNode={setSelected}
        />
        <GraphChatPanel
          settings={settings}
          onHighlightNodes={setHighlighted}
          onSelectNode={setSelected}
        />
      </div>
      <div className="graph-page-status"> ... </div>
    </div>
  )
}
```

#### Step 3: GraphLeftPanel.jsx (mới) — Search + Document list + Detail

**File tạo mới**: `frontend/src/components/GraphLeftPanel.jsx`

2 chế độ:
1. **List mode** (mặc định): search box + danh sách documents
   - Mỗi item: icon + filename + chunk count + size
   - Click → `onSelectNode(node)` → center camera + hiện detail
   - Search filter real-time (text match trên filename)
2. **Detail mode** (khi `selected` !== null): metadata + neighbors list
   - Filename, folder, chunks, size, uploaded date
   - Neighbors sorted by similarity (click → navigate)
   - Nút "← All documents" quay lại list mode

Tái sử dụng logic từ `GraphDetailPanel.jsx` hiện tại (merge vào).

#### Step 4: GraphCanvas.jsx (mới) — Graph rendering tách riêng

**File tạo mới**: `frontend/src/components/GraphCanvas.jsx`

Tách phần ForceGraph2D ra khỏi GraphPanel cũ:
- Nhận `data`, `selected`, `highlighted`, `onSelectNode` qua props
- Giữ nguyên: `nodeCanvasObject`, `nodePointerAreaPaint`, `linkColor`, hover highlight, neighbor adjacency map
- Thêm: highlight nodes từ AI chat (dùng `highlighted` array — ring xanh dương)
- Floating button "Fit" (zoom-to-fit) ở góc phải dưới
- GraphLegend floating ở góc trái dưới
- Khi `selected` thay đổi → `centerAt(node.x, node.y, 500)`

#### Step 5: GraphChatPanel.jsx (mới) — AI Chat sidebar

**File tạo mới**: `frontend/src/components/GraphChatPanel.jsx`

Mini chat window tái sử dụng `useAgent` hook:
- Header: "Ask JARVIS about documents"
- Message list: scroll, markdown rendering (tái sử dụng MessageBubble đơn giản)
- Input bar: text input + send button
- Khi AI trả lời có nhắc đến document filename → parse ra → `onHighlightNodes([ids])`
- Hiện related documents dưới response (clickable → `onSelectNode`)

Backend: dùng endpoint `/api/agent/execute` hiện tại — agent đã có `rag_search` tool, sẽ tự dùng khi câu hỏi liên quan tài liệu.

Logic highlight:
```js
// Sau khi nhận response từ agent
const mentionedDocs = data.nodes.filter(n =>
  response.toLowerCase().includes(n.label.toLowerCase())
)
onHighlightNodes(mentionedDocs.map(n => n.id))
```

#### Step 6: useGraph.js — Đơn giản hoá

**File sửa**: `frontend/src/hooks/useGraph.js`

- Bỏ `threshold` state + `setThreshold` (hardcode 0.5)
- Bỏ `rebuild` function (user không cần)
- API call: `GET /api/graph/data?threshold=0.5` (fixed)
- Giữ: data fetch, loading, error, auto-refresh khi document upload/delete

#### Step 7: Xoá/cleanup components cũ

**Files xoá**:
- `frontend/src/components/GraphToolbar.jsx` — không cần (search chuyển vào left panel, bỏ threshold/rebuild)
- `frontend/src/components/GraphPanel.jsx` — thay thế bởi `GraphPage.jsx`
- `frontend/src/components/GraphDetailPanel.jsx` — merge vào `GraphLeftPanel.jsx`

#### Step 8: CSS — Graph page dark theme

**File sửa**: `frontend/src/main.css`

Thêm styles cho:
- `.graph-page` — full viewport, flex column
- `.graph-page-header` — dark bar, nút Back, tiêu đề
- `.graph-page-body` — flex row, 3 columns
- `.graph-left-panel` — 280px, dark bg #1a1b22, border-right, overflow-y scroll
- `.graph-canvas` — flex 1, bg #0f1014
- `.graph-chat-panel` — 360px, dark bg #1a1b22, border-left, flex column
- `.graph-page-status` — bottom bar, stats
- Responsive: trên mobile (< 768px) — left panel hidden by default, toggle via icon

Xoá: styles cũ cho `.documents-modal` (đã fix ở session trước — giữ), graph-related modal styles không còn dùng.

#### Step 9: i18n

**Files sửa**: `frontend/src/i18n/en.json`, `frontend/src/i18n/vi.json`

Thêm keys:
```json
{
  "graph.pageTitle": "Graph View",
  "graph.back": "Back to Chat",
  "graph.searchDocs": "Search documents...",
  "graph.allDocuments": "All documents",
  "graph.selectedDoc": "Selected document",
  "graph.askJarvis": "Ask JARVIS about documents...",
  "graph.aiChatTitle": "Document AI",
  "graph.noDocsYet": "Upload documents to see the knowledge graph",
  "graph.statusBar": "{{docs}} docs · {{links}} links"
}
```

#### Step 10: Docs sync + E2E test

- `docs/technical_reference.md` — cập nhật section 8 (Frontend Architecture) cho 3-panel layout
- `README.md` — cập nhật mô tả Knowledge Graph feature
- `task.md` — đánh dấu [x] từng task
- E2E test: Playwright test verify graph page load, left panel visible, chat panel visible

### Dependencies giữa các steps

```
Step 1 (App.jsx)  ──→  Step 2 (GraphPage.jsx)  ──→  Step 3 (LeftPanel)
                                                ──→  Step 4 (Canvas)
                                                ──→  Step 5 (ChatPanel)
Step 6 (useGraph) ── có thể làm song song ──
Step 7 (cleanup)  ── sau khi Step 2-5 xong ──
Step 8 (CSS)      ── song song với Step 2-5 ──
Step 9 (i18n)     ── song song ──
Step 10 (docs)    ── cuối cùng ──
```

### Rủi ro & giải pháp

| Rủi ro | Mức | Giải pháp |
|---|---|---|
| Chat sidebar tải nặng khi graph lớn | MEDIUM | Tách `useAgent` instance riêng cho GraphChatPanel, không share state với ChatArea chính |
| Graph re-render khi AI chat cập nhật highlighted | LOW | Dùng `useMemo` + `useCallback` như hiện tại, chỉ truyền `highlighted` array (shallow compare) |
| Mobile 3 panel không fit | MEDIUM | Responsive: mobile → chỉ hiện graph + floating toggles cho left/right panel |
| AI highlight sai doc (tên file trùng substring) | LOW | Match exact filename, case-insensitive |
| Mất backward compat với GraphPanel E2E test cũ | LOW | Viết test mới cho GraphPage, xoá test cũ |

### Thư viện mới cần thêm

Không cần thêm dependency mới. Tất cả dựa trên:
- `react-force-graph-2d` (đã có)
- `react-bootstrap` (đã có)
- `useAgent` hook (đã có)
- `lucide-react` icons (đã có)

### Ước tính khối lượng

| Step | File | Dòng code mới/sửa | Độ phức tạp |
|---|---|---|---|
| 1 | App.jsx | ~30 sửa | Low |
| 2 | GraphPage.jsx | ~120 mới | Medium |
| 3 | GraphLeftPanel.jsx | ~200 mới | Medium |
| 4 | GraphCanvas.jsx | ~180 mới (refactor từ GraphPanel) | Medium |
| 5 | GraphChatPanel.jsx | ~180 mới | Medium |
| 6 | useGraph.js | ~20 sửa | Low |
| 7 | Cleanup (xoá 3 file) | -350 xoá | Low |
| 8 | main.css | ~150 mới | Medium |
| 9 | en.json + vi.json | ~20 mới | Low |
| 10 | Docs + E2E | ~100 | Low |
| **Tổng** | | **~1000 net new** | **Medium** |

---

## Phase 10: AI Auto-Convert Pipeline — Wikilinks + Hybrid Graph

### Mục tiêu

Khi user upload PDF/DOCX/PPTX/XLSX, hệ thống tự động:
1. Convert sang clean Markdown (giữ structure)
2. Gọi LLM chèn `[[wikilinks]]` vào markdown (entities, concepts, organizations)
3. Lưu .md vào vault/ folder
4. Parse `[[wikilinks]]` → explicit edges (nét liền) trên graph
5. Kết hợp với cosine similarity → implicit edges (nét đứt) — đã có từ Phase 8
6. Build backlinks index (ai link đến file này?)

Fallback: nếu không có LLM API key → bỏ qua bước 2, chỉ dùng cosine (như cũ).

### Pipeline tổng quan

```
Upload file (PDF/DOCX/PPTX/XLSX/TXT/MD)
    │
    ▼
[Existing] Save file + parse chunks + embed → ChromaDB (giữ nguyên)
    │
    ▼
[New — background task, async]
    │
    ├─► [Step A] MarkItDown convert → clean Markdown
    │       Input:  backend/uploads/{doc_id}.ext
    │       Output: raw markdown string
    │
    ├─► [Step B] LLM chèn [[wikilinks]]
    │       Input:  raw markdown (chunk nếu > 4000 tokens)
    │       Prompt: "Identify entities, insert [[WikiLink]] around first occurrence"
    │       Output: markdown có [[links]]
    │
    ├─► [Step C] Lưu vault/{doc_id}.md
    │       Cũng update documents_metadata.json: thêm vault_file, links[]
    │
    └─► [Step D] Invalidate graph cache → next request sẽ rebuild với explicit edges
```

Upload response trả ngay `200 OK` (không đợi LLM). Background task chạy Step A-D.
Metadata cập nhật `status: "processing" → "ready"` khi xong.

### Chọn thư viện convert: MarkItDown (Microsoft)

| Tiêu chí | MarkItDown | Marker |
|---|---|---|
| Accuracy | Tốt cho DOCX/PPTX/XLSX, OK cho PDF | Tốt nhất cho PDF (95.67%) |
| Size | Nhẹ (~2 MB) | Nặng (~500 MB, cần torch) |
| Install | `pip install markitdown` | `pip install marker-pdf` + torch |
| Speed | Nhanh (< 2s cho 100 trang) | Chậm hơn (5-15s, dùng model vision) |
| Dependencies | Minimal (docx, pptx, openpyxl) | Nặng (torch, layoutparser, tesseract) |

**Chọn MarkItDown** vì:
- Project đã có torch cho sentence-transformers nhưng MarkItDown nhẹ hơn, nhanh hơn
- DOCX/PPTX/XLSX convert rất tốt (cùng thư viện python-docx, openpyxl mà project đang dùng)
- PDF convert OK cho text-based PDF (hầu hết tài liệu business)
- Không cần GPU
- Có thể upgrade sang Marker cho PDF nặng sau nếu cần

### Chi tiết từng step

#### Step 1: Install MarkItDown

**File sửa**: `backend/requirements.txt`

```
markitdown>=0.1.0
```

#### Step 2: md_converter.py — Convert file → Markdown

**File tạo mới**: `backend/app/rag/md_converter.py`

```python
"""Convert uploaded documents to clean Markdown using MarkItDown."""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MarkdownConverter:
    """Wrapper around MarkItDown for async document → Markdown conversion."""

    async def convert(self, file_path: str) -> str:
        """Convert a document file to Markdown text.

        Runs synchronously in a thread pool to avoid blocking the event loop.
        Returns empty string on failure (non-fatal — graph still works via cosine).
        """
        return await asyncio.to_thread(self._convert_sync, file_path)

    def _convert_sync(self, file_path: str) -> str:
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            result = md.convert(file_path)
            text = result.text_content or ""
            logger.info("Converted '%s' → %d chars Markdown", Path(file_path).name, len(text))
            return text
        except Exception as exc:
            logger.warning("MarkItDown conversion failed for '%s': %s", file_path, exc)
            return ""
```

#### Step 3: wikilink_generator.py — LLM chèn [[wikilinks]]

**File tạo mới**: `backend/app/rag/wikilink_generator.py`

```python
"""Use LLM to extract entities and insert [[wikilinks]] into Markdown."""

import asyncio
import logging
from app.agent.brain import _build_llm
from app.core.config import settings

logger = logging.getLogger(__name__)

WIKILINK_PROMPT = '''You are a knowledge organizer. Read the document below and:

1. Identify all key entities: people, organizations, technologies, concepts, products, standards.
2. For each entity, create a canonical wiki page name in PascalCase (e.g., "FastAPI", "ChromaDB").
3. Insert [[WikiPageName]] around the FIRST occurrence of each entity only.
4. Do NOT modify the document text — only add [[ ]] brackets.
5. Return the FULL document with [[wikilinks]] inserted. No commentary.

Document:
---
{content}
---

Return the document with [[wikilinks]]:'''

# Max tokens per chunk sent to LLM (leave room for prompt + response)
_CHUNK_MAX_CHARS = 12000


class WikilinkGenerator:
    """Generate [[wikilinks]] in Markdown using an LLM."""

    async def generate(self, markdown: str, provider: str = None, model: str = None) -> str:
        """Insert [[wikilinks]] into markdown using configured LLM.

        For documents exceeding _CHUNK_MAX_CHARS, processes in chunks and merges.
        Returns original markdown on any failure (non-fatal).
        """
        provider = provider or settings.default_provider
        model = model or settings.default_model

        try:
            llm = _build_llm(provider, model)
        except Exception as exc:
            logger.warning("Cannot build LLM for wikilinks (provider=%s): %s", provider, exc)
            return markdown

        chunks = self._split_for_llm(markdown)
        results = []
        seen_entities = set()

        for i, chunk in enumerate(chunks):
            prompt = WIKILINK_PROMPT.format(content=chunk)
            if seen_entities:
                prompt += f"\n\nEntities already linked in previous chunks (do NOT re-link): {', '.join(sorted(seen_entities))}"

            try:
                response = await asyncio.to_thread(self._call_llm_sync, llm, prompt)
                results.append(response)
                # Track entities found in this chunk
                import re
                for match in re.finditer(r'\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]', response):
                    seen_entities.add(match.group(1))
            except Exception as exc:
                logger.warning("LLM wikilink generation failed for chunk %d: %s", i, exc)
                results.append(chunk)  # fallback: original text

        merged = "\n\n".join(results)
        logger.info("Wikilink generation complete: %d entities found", len(seen_entities))
        return merged

    def _call_llm_sync(self, llm, prompt: str) -> str:
        """Synchronous LLM call — runs in thread pool."""
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        if isinstance(content, list):
            parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
            return "\n".join(parts)
        return str(content)

    @staticmethod
    def _split_for_llm(text: str) -> list[str]:
        """Split text into chunks of at most _CHUNK_MAX_CHARS on paragraph boundaries."""
        if len(text) <= _CHUNK_MAX_CHARS:
            return [text]
        chunks = []
        while text:
            if len(text) <= _CHUNK_MAX_CHARS:
                chunks.append(text)
                break
            split_at = text.rfind("\n\n", 0, _CHUNK_MAX_CHARS)
            if split_at == -1:
                split_at = text.rfind("\n", 0, _CHUNK_MAX_CHARS)
            if split_at == -1:
                split_at = _CHUNK_MAX_CHARS
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks
```

#### Step 4: link_extractor.py — Parse [[wikilinks]] từ .md

**File tạo mới**: `backend/app/graph/link_extractor.py`

```python
"""Extract [[wikilinks]] from Markdown text using regex."""

import re

WIKILINK_PATTERN = re.compile(r'(?<!!)\[\[([^|\]]+?)(?:\|([^\]]+?))?\]\]')


def extract_wikilinks(markdown: str, source_doc_id: str = "") -> list[dict]:
    """Extract [[Target]] and [[Target|Display]] from markdown.

    Returns list of dicts: [{target, display, context, source_doc_id}]
    """
    links = []
    seen_targets = set()
    for match in WIKILINK_PATTERN.finditer(markdown):
        target = match.group(1).strip()
        display = (match.group(2) or target).strip()
        if target in seen_targets:
            continue  # deduplicate within same doc
        seen_targets.add(target)
        start = max(0, match.start() - 60)
        end = min(len(markdown), match.end() + 60)
        context = markdown[start:end].replace("\n", " ").strip()
        links.append({
            "target": target,
            "display": display,
            "context": context,
            "source_doc_id": source_doc_id,
        })
    return links
```

#### Step 5: Sửa documents.py — Upload pipeline + background task

**File sửa**: `backend/app/routers/documents.py`

Thêm vào sau dòng `invalidate_graph_cache()`:

```python
from fastapi import BackgroundTasks

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    # ... existing code (save file, parse chunks, embed, ChromaDB) ...

    # NEW: background task — convert to .md + LLM wikilinks
    if background_tasks:
        background_tasks.add_task(
            _process_vault_file,
            doc_id=doc_id,
            file_path=str(file_path),
            filename=file.filename or "",
        )

    return DocumentUploadResponse(...)


async def _process_vault_file(doc_id: str, file_path: str, filename: str):
    """Background: convert → LLM wikilinks → save vault .md → update metadata."""
    from app.rag.md_converter import MarkdownConverter
    from app.rag.wikilink_generator import WikilinkGenerator
    from app.graph.link_extractor import extract_wikilinks
    from app.graph.cache import invalidate_cache as invalidate_graph_cache

    converter = MarkdownConverter()
    md_text = await converter.convert(file_path)
    if not md_text:
        return  # conversion failed — cosine-only graph still works

    generator = WikilinkGenerator()
    md_with_links = await generator.generate(md_text)

    # Save to vault/
    vault_dir = Path(settings.upload_dir) / "vault"
    vault_dir.mkdir(exist_ok=True)
    vault_path = vault_dir / f"{doc_id}.md"
    vault_path.write_text(md_with_links, encoding="utf-8")

    # Extract links + update metadata
    links = extract_wikilinks(md_with_links, source_doc_id=doc_id)
    docs = _load_metadata()
    for doc in docs:
        if doc["id"] == doc_id:
            doc["vault_file"] = str(vault_path)
            doc["wikilinks"] = [{"target": l["target"], "context": l["context"]} for l in links]
            doc["status"] = "ready"
            break
    _save_metadata(docs)

    invalidate_graph_cache()
    logger.info("Vault file ready for '%s': %d wikilinks extracted", filename, len(links))
```

#### Step 6: Sửa graph/builder.py — Hybrid edges

**File sửa**: `backend/app/graph/builder.py`

Thêm logic merge explicit + implicit edges:

```python
# After computing cosine similarity links...

# Load explicit links from metadata wikilinks field
explicit_links = []
for doc in docs:
    for wl in doc.get("wikilinks", []):
        # Resolve wikilink target name → document ID (fuzzy match on filename)
        target_id = _resolve_link_target(wl["target"], docs)
        if target_id and target_id != doc["id"]:
            explicit_links.append(GraphLink(
                source=doc["id"],
                target=target_id,
                weight=1.0,
                link_type="explicit",
                context=wl.get("context", ""),
            ))

# Dedup: if explicit link A→B exists, remove implicit A→B
explicit_pairs = {(l.source, l.target) for l in explicit_links}
explicit_pairs |= {(l.target, l.source) for l in explicit_links}  # bidirectional
implicit_links = [l for l in cosine_links if (l.source, l.target) not in explicit_pairs]

# Tag implicit links
for l in implicit_links:
    l.link_type = "implicit"

all_links = explicit_links + implicit_links
```

#### Step 7: Sửa GraphLink schema

**File sửa**: `backend/app/models/graph_schemas.py`

```python
class GraphLink(BaseModel):
    source: str
    target: str
    weight: float
    link_type: str = "implicit"   # "explicit" (wikilink) | "implicit" (cosine)
    context: str | None = None    # text around [[link]] for explicit
```

#### Step 8: Frontend — Edge styles + Backlinks

**File sửa**: `frontend/src/components/GraphCanvas.jsx`

```jsx
// linkLineDash callback: explicit = solid, implicit = dashed
const linkLineDash = useCallback(
  (link) => link.link_type === 'implicit' ? [4, 2] : null,
  []
)

// Add prop to ForceGraph2D:
<ForceGraph2D linkLineDash={linkLineDash} ... />
```

**File sửa**: `frontend/src/components/GraphLeftPanel.jsx`

Thêm section "Backlinks" trong detail mode — docs có wikilink trỏ đến node này.

#### Step 9: Vault viewer endpoint

**File tạo mới**: `backend/app/routers/vault.py`

```python
@router.get("/api/vault/{doc_id}")
async def get_vault_file(doc_id: str):
    """Return the converted Markdown content of a document."""
    vault_path = Path(settings.upload_dir) / "vault" / f"{doc_id}.md"
    if not vault_path.exists():
        raise HTTPException(404, "Vault file not found — document may still be processing.")
    return {"doc_id": doc_id, "content": vault_path.read_text(encoding="utf-8")}
```

### Files tạo/sửa/xoá tổng hợp

| Action | File | Mô tả |
|---|---|---|
| **Tạo** | `backend/app/rag/md_converter.py` | MarkItDown wrapper |
| **Tạo** | `backend/app/rag/wikilink_generator.py` | LLM chèn [[wikilinks]] |
| **Tạo** | `backend/app/graph/link_extractor.py` | Regex parse [[...]] |
| **Tạo** | `backend/app/routers/vault.py` | GET /api/vault/{doc_id} |
| **Sửa** | `backend/requirements.txt` | Thêm `markitdown` |
| **Sửa** | `backend/app/routers/documents.py` | Background task pipeline |
| **Sửa** | `backend/app/graph/builder.py` | Merge explicit + implicit edges |
| **Sửa** | `backend/app/models/graph_schemas.py` | GraphLink + link_type/context |
| **Sửa** | `backend/app/main.py` | Register vault router |
| **Sửa** | `frontend/src/components/GraphCanvas.jsx` | Edge line dash by type |
| **Sửa** | `frontend/src/components/GraphLeftPanel.jsx` | Backlinks section |

### Dependencies giữa các steps

```
Step 1 (install)     ──→ Step 2 (converter)
Step 2 (converter)   ──→ Step 5 (upload pipeline)
Step 3 (wikilinks)   ──→ Step 5 (upload pipeline)
Step 4 (extractor)   ──→ Step 5 (upload pipeline)
Step 5 (pipeline)    ──→ Step 6 (builder)
Step 7 (schema)      ──→ Step 6 (builder) + Step 8 (frontend)
Step 9 (vault API)   ── song song ──
```

### Rủi ro & giải pháp

| Rủi ro | Mức | Giải pháp |
|---|---|---|
| LLM hallucinate entity → link sai | MEDIUM | User có thể GET vault .md để review; fallback: cosine vẫn hoạt động |
| File 200 trang vượt context window | MEDIUM | Chunk markdown ≤ 12K chars, process lần lượt, track seen_entities |
| MarkItDown fail format lạ | LOW | Return empty string → skip wikilinks, cosine-only |
| Background task fail | LOW | Non-fatal: log warning, graph vẫn build từ cosine |
| Upload latency tăng | LOW | Background task — response trả ngay 200, LLM chạy sau |
| Không có LLM key | LOW | Skip wikilink step hoàn toàn, code path giống Phase 8 |

### Thư viện mới

```
markitdown>=0.1.0    # Microsoft MarkItDown — PDF/DOCX/PPTX/XLSX → Markdown
```

### Ước tính khối lượng

| Step | File | Dòng | Phức tạp |
|---|---|---|---|
| 1 | requirements.txt | 1 | Low |
| 2 | md_converter.py | ~40 | Low |
| 3 | wikilink_generator.py | ~100 | Medium |
| 4 | link_extractor.py | ~40 | Low |
| 5 | documents.py sửa | ~50 | Medium |
| 6 | builder.py sửa | ~60 | Medium |
| 7 | graph_schemas.py sửa | ~5 | Low |
| 8 | GraphCanvas + LeftPanel sửa | ~30 | Low |
| 9 | vault.py | ~25 | Low |
| Tests | test_link_extractor, test_converter | ~80 | Medium |
| **Tổng** | | **~430 net new** | **Medium** |
