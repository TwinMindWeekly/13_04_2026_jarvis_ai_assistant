# JARVIS AI Assistant

> Trợ lý AI có khả năng thực thi hành động: duyệt web, tìm kiếm, đọc tài liệu RAG, thao tác máy tính — lấy cảm hứng từ JARVIS (Iron Man).

## Giới thiệu

JARVIS AI Assistant không phải chatbot thông thường — nó là một **agent** có thể chủ động gọi tool để hoàn thành yêu cầu người dùng:

- **Web search** — tìm thông tin internet (DuckDuckGo, không cần API key)
- **Web browser** — mở URL, đọc nội dung trang, chụp ảnh trang
- **Browser control** — tự động hoá thao tác trình duyệt theo DOM/accessibility (kiểu OpenClaw)
- **Desktop control** — chụp màn hình + click/type qua PyAutoGUI (có Safety Layer)
- **File manager** — đọc/ghi file trong sandbox đã whitelist
- **App launcher** — mở ứng dụng theo whitelist
- **RAG search** — trả lời dựa trên tài liệu PDF/DOCX/PPTX/XLSX/MD/TXT do người dùng upload
- **Knowledge Graph** — đồ thị tương tác kiểu Obsidian hiển thị mối quan hệ giữa các tài liệu (cosine similarity), drag/zoom/pan mượt đến hàng ngàn nodes
- **Voice I/O** — nói/nghe bằng Web Speech API + SpeechSynthesis (browser native)

## Công nghệ sử dụng

### Backend (Python 3.11+)
| Stack | Phiên bản | Vai trò |
|-------|-----------|---------|
| FastAPI | 0.115+ | REST + WebSocket + SSE streaming |
| Pydantic v2 | 2.10+ | Schema validation |
| LangGraph | 0.2+ | ReAct agent loop (`create_react_agent`) |
| LangChain Core | 0.3+ | Tool/message abstractions |
| Playwright | 1.49+ | Browser automation (Chromium headless) |
| ChromaDB | 1.5+ | Vector database (persistent local) |
| sentence-transformers | 5.0+ | Embeddings local (all-MiniLM-L6-v2) |
| unstructured | 0.16+ | Parser PDF/DOCX/PPTX/XLSX |
| PyAutoGUI | 0.9.54+ | Desktop control |
| mss | 9.0+ | Screenshot cross-platform |
| duckduckgo-search | 7.0+ | Search fallback (no key) |

### Frontend (React 19 + Vite 8)
| Stack | Phiên bản | Vai trò |
|-------|-----------|---------|
| React | 19.2 | UI framework |
| Vite | 8.0 | Build tool / dev server |
| Bootstrap | 5.3 + react-bootstrap | UI components (ChatGPT-style layout) |
| framer-motion | 12 | Animations |
| lucide-react | 1.8 | Icon set |
| react-markdown + remark-gfm | 10 / 4 | Markdown rendering |
| i18next + react-i18next | 26 / 17 | EN/VI bilingual |
| Web Speech API | native | STT (SpeechRecognition) |
| SpeechSynthesis | native | TTS browser native |

### LLM Providers (Multi-provider Factory)
| Provider | Models tested | Tool use | Ghi chú |
|----------|--------------|----------|---------|
| **OpenAI** | gpt-4o, gpt-4o-mini | Đầy đủ | Khuyến nghị cho computer-use tools |
| **Google Gemini** | gemini-2.5-flash, gemini-2.5-pro | Hạn chế | Safety filter chặn local control tools (chỉ cho phép web_search, rag_search) |
| **Anthropic Claude** | claude-sonnet-4-5 | Đầy đủ | Cần ANTHROPIC_API_KEY |
| **Ollama** | llama3, qwen2.5 | Tuỳ model | Local, không cần internet |

## Kiến trúc hệ thống

```
┌────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite 8 + Bootstrap)                  │
│  ┌──────────┐ ┌──────────────┐ ┌────────────────────────┐  │
│  │ ChatArea │ │ ActionViewer │ │ DocumentsPanel (RAG)   │  │
│  │ Sidebar  │ │ SettingsPanel│ │ VoiceButton (mic+TTS)  │  │
│  └──────────┘ └──────────────┘ └────────────────────────┘  │
└────────────────────────┬───────────────────────────────────┘
                         │ REST + SSE + WebSocket
┌────────────────────────▼───────────────────────────────────┐
│  Backend (FastAPI, async-first)                            │
│  Routers: /api/chat /api/agent /api/providers /api/documents│
│           /ws/agent                                         │
├────────────────────────────────────────────────────────────┤
│  Agent Brain — LangGraph ReAct (create_react_agent)        │
│  Think → Act → Observe → Loop (max 10 iterations)          │
├────────────────────────────────────────────────────────────┤
│  Tool Registry (8 tools)                                   │
│  ├── web_search       ├── web_browser    ├── screenshot    │
│  ├── browser_control  ├── desktop_control├── file_manager  │
│  ├── app_launcher     └── rag_search                       │
├────────────────────────────────────────────────────────────┤
│  Safety Layer (4 levels: AUTO / NOTIFY / CONFIRM / BLOCK)  │
├────────────────────────────────────────────────────────────┤
│  LLM Factory (provider-agnostic)                           │
│  └── _build_llm(provider, model) → ChatOpenAI/Gemini/      │
│      Anthropic/ChatOllama (via OpenAI-compatible)          │
├────────────────────────────────────────────────────────────┤
│  RAG Pipeline                                              │
│  Upload → unstructured.partition → chunk → embed (MiniLM)  │
│  → ChromaDB (PersistentClient, per-doc collection)         │
└────────────────────────────────────────────────────────────┘
```

## Cách chạy dự án

### Yêu cầu
- Python 3.11+ (khuyến nghị 3.13)
- Node.js 20+
- Windows / Linux / macOS

### Cách 1 — Script tự động (Windows)

```bat
start.bat   # Tạo venv, cài deps, install playwright chromium, chạy backend + frontend
stop.bat    # Tắt cả hai dev server
```

`start.bat` sẽ mở Windows Terminal split panes nếu có, fallback về 2 cmd window riêng.

### Cách 2 — Thủ công

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate      # Linux/macOS
pip install -r requirements.txt
playwright install chromium
cp .env.example .env            # Điền API keys
uvicorn app.main:app --reload --port 8000

# Frontend (terminal mới)
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

### Biến môi trường (`backend/.env`)

```env
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...
# OLLAMA_BASE_URL=http://localhost:11434  (mặc định, có thể bỏ)

DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-4o-mini
```

Chỉ cần ít nhất **1 API key** để chạy. Provider có thể đổi runtime từ Settings panel.

## Tính năng UI (ChatGPT-style)

- **Empty state** — input căn giữa, prompt "What's on the agenda today?"
- **Chat layout** — full-width messages (không bubble), input sticky bottom max-w 768px
- **Action Viewer** — hiển thị từng tool call (icon → input → output) collapsible
- **Settings panel** — chọn provider/model, test connection, đổi ngôn ngữ EN/VI
- **Documents panel** — upload PDF/DOCX/PPTX/XLSX/MD/TXT, list, delete; tự động vào ChromaDB
- **Voice** — nút mic (STT) + auto-TTS khi assistant phản hồi
- **i18n** — Tiếng Việt / English (chuyển trong Settings)

## Trạng thái dự án

Tất cả 7 phase đã hoàn thành. Xem [task.md](./task.md) và [implementation_plan.md](./implementation_plan.md) cho chi tiết.

## Tài liệu

- [Technical Reference](./docs/technical_reference.md) — API, tool spec, message protocol
- [Project Scope & Tech](./docs/project_scope_and_tech.md) — phạm vi & lựa chọn công nghệ
- [Known Issues & Learnings](./docs/known_issues_and_learnings.md) — nhật ký bug + bài học
- [AI Agent Protocol](./AI_AGENT_PROTOCOL.md) — quy trình phát triển

## License

MIT
