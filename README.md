# JARVIS AI Assistant

> Trợ lý AI thông minh có khả năng thực thi hành động: duyệt web, tìm kiếm, thao tác máy tính - lấy cảm hứng từ JARVIS (Iron Man).

## Giới thiệu

JARVIS AI Assistant là một hệ thống trợ lý AI đa năng, vượt xa chatbot truyền thống. Thay vì chỉ trả lời câu hỏi, JARVIS có thể **thực hiện hành động** thay cho người dùng:

- **Duyệt web**: Mở trang web, đọc nội dung, điền form
- **Tìm kiếm**: Tìm kiếm thông tin trên internet theo yêu cầu
- **Thao tác máy tính**: Chụp màn hình, click, gõ phím
- **Hội thoại giọng nói**: Giao tiếp bằng giọng nói real-time
- **RAG**: Truy xuất và trả lời dựa trên tài liệu riêng

## Công nghệ sử dụng

### Backend
| Công nghệ | Phiên bản | Mục đích |
|-----------|-----------|----------|
| Python | 3.11+ | Ngôn ngữ chính |
| FastAPI | 0.115+ | REST API + WebSocket |
| LangChain | 0.3+ | Agent orchestration, Tool use |
| LangGraph | 0.2+ | Multi-step agent workflow |
| Playwright | 1.49+ | Browser automation |
| ChromaDB | 0.5+ | Vector database cho RAG |

### Frontend
| Công nghệ | Phiên bản | Mục đích |
|-----------|-----------|----------|
| React | 19 | UI framework |
| Vite | 6+ | Build tool |
| Web Speech API | - | Voice input/output |
| WebSocket | - | Real-time communication |

### AI Providers (Multi-provider Factory)
- **OpenAI** (GPT-4o) - Function calling + Vision
- **Google Gemini** (2.0 Flash) - Multimodal + Function calling
- **Anthropic Claude** (Sonnet 4) - Computer Use + Tool use
- **Ollama** (Local) - Privacy-first, offline mode

## Kiến trúc hệ thống

```
┌──────────────────────────────────────────────┐
│              JARVIS Frontend                  │
│   React + Voice I/O + Chat + Action Viewer   │
└──────────────┬───────────────────────────────┘
               │ WebSocket + REST API
┌──────────────▼───────────────────────────────┐
│              JARVIS Backend (FastAPI)          │
├───────────────────────────────────────────────┤
│  Agent Brain (LangGraph)                      │
│  ├── Planner: Phân tích yêu cầu              │
│  ├── Executor: Thực thi tool                  │
│  └── Reviewer: Đánh giá kết quả              │
├───────────────────────────────────────────────┤
│  Tool Registry                                │
│  ├── WebBrowser (Playwright)                  │
│  ├── WebSearch (Google/Bing API)              │
│  ├── ScreenCapture + ComputerUse             │
│  ├── FileManager (đọc/ghi file)              │
│  └── RAGRetriever (ChromaDB)                 │
├───────────────────────────────────────────────┤
│  LLM Provider Factory                         │
│  ├── OpenAI  ├── Gemini  ├── Claude  ├── Ollama│
└───────────────────────────────────────────────┘
```

## Cách chạy dự án

### Yêu cầu hệ thống
- Python 3.11+
- Node.js 20+
- Git

### Cài đặt và khởi chạy

```bash
# 1. Clone repository
git clone https://github.com/TwinMindWeekly/13_04_2026_jarvis_ai_assistant.git
cd 13_04_2026_jarvis_ai_assistant

# 2. Cài đặt Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Cấu hình môi trường
cp .env.example .env
# Điền API keys vào file .env

# 4. Khởi chạy Backend
uvicorn app.main:app --reload --port 8000

# 5. Cài đặt Frontend (terminal mới)
cd frontend
npm install
npm run dev
```

### Biến môi trường (.env)
```env
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...
# Ollama không cần key (chạy local)
```

## Trạng thái dự án

Xem chi tiết tại [task.md](./task.md) và [implementation_plan.md](./implementation_plan.md).

## Tài liệu tham khảo

- [Technical Reference](./docs/technical_reference.md)
- [Project Scope & Tech](./docs/project_scope_and_tech.md)
- [Known Issues & Learnings](./docs/known_issues_and_learnings.md)

## License

MIT
