# JARVIS AI Assistant - Project Scope & Technology Decisions

> Phạm vi dự án và các quyết định công nghệ.
> Cập nhật lần cuối: 15/04/2026

---

## 1. Phạm vi dự án (Project Scope)

### Trong phạm vi (In Scope)
- Trợ lý AI có khả năng thực thi hành động (agent-based)
- Duyệt web: mở URL, đọc nội dung, tương tác với trang web
- Tìm kiếm internet: Google, Bing, DuckDuckGo
- Thao tác máy tính: chụp màn hình, click, gõ phím (có xác nhận)
- Giao tiếp giọng nói: STT + TTS
- RAG: trả lời dựa trên tài liệu người dùng upload
- Multi-provider LLM: OpenAI, Gemini, Claude, Ollama
- Giao diện web hiện đại (React + glassmorphism)

### Ngoài phạm vi (Out of Scope)
- Mobile app (chỉ web app)
- Self-hosted LLM training
- Multi-user / authentication system (single-user local app)
- Cloud deployment (chạy local-first)
- Tích hợp email / calendar / social media (có thể mở rộng sau)

---

## 2. Quyết định công nghệ (Technology Decisions)

### Backend Framework: FastAPI

**Lý do chọn:**
- Async native (phù hợp với tool execution + streaming)
- WebSocket support built-in
- Pydantic integration cho type safety
- Đã được sử dụng trong dự án `06_04_2026_multimodal_rag_ai` → tái sử dụng kinh nghiệm

**Alternatives đã cân nhắc:**
- Flask: Không async native, không hỗ trợ WebSocket tốt
- Django: Quá nặng cho ứng dụng AI assistant
- Node.js/Express: Đội ngũ quen Python hơn

### Agent Framework: LangGraph

**Lý do chọn:**
- ReAct agent loop có sẵn, dễ customize
- State management cho multi-step workflows
- Tích hợp tốt với LangChain tools
- Hỗ trợ streaming và human-in-the-loop

**Alternatives đã cân nhắc:**
- LangChain AgentExecutor: Đang deprecated, LangGraph thay thế
- CrewAI: Quá phức tạp cho single-agent use case
- AutoGen: Thiên về multi-agent, không cần thiết ở giai đoạn đầu
- Custom ReAct loop: Tốn thời gian, LangGraph đã giải quyết tốt

### Browser Automation: Playwright

**Lý do chọn:**
- Cross-browser support (Chromium, Firefox, WebKit)
- Async API phù hợp FastAPI
- Headless mode cho server-side
- Screenshot, PDF, network interception built-in
- Đã quen thuộc từ E2E testing

**Alternatives đã cân nhắc:**
- Selenium: API cũ, không async
- Puppeteer: Chỉ hỗ trợ Chromium
- Splash: Quá hạn chế

### Frontend: React 19 + Vite

**Lý do chọn:**
- Component-based architecture phù hợp cho UI phức tạp
- Ecosystem lớn (markdown renderer, i18n, animation)
- Đã sử dụng trong dự án RAG → tái sử dụng components
- Vite: build nhanh, HMR tốt

### Voice: Web Speech API + OpenAI TTS

**Lý do chọn:**
- Web Speech API: Miễn phí, chạy trên browser, không cần server
- OpenAI TTS: Giọng tự nhiên, hỗ trợ tiếng Việt
- Fallback chain: Browser native → Cloud API

### Tại sao KHÔNG dùng trực tiếp NVIDIA PersonaPlex?

| Yếu tố | PersonaPlex | JARVIS cần |
|---------|:-----------:|:----------:|
| Mục đích | Speech-to-speech model | Agent thực thi hành động |
| GPU yêu cầu | NVIDIA GPU + CUDA 12.4+ | Có thể chạy CPU (dùng API) |
| Khả năng tool use | Không có | Cốt lõi |
| Độ phức tạp deploy | Rất cao (7B model) | Nhẹ (API calls) |

**Bài học rút ra từ PersonaPlex:**
1. Binary WebSocket protocol cho real-time audio → áp dụng cho Phase 4
2. AudioWorklet pattern trên browser → tham khảo cho voice streaming
3. Factory pattern cho voice/persona switching → áp dụng cho LLM provider
4. Streaming state management → tham khảo cho agent state

---

## 3. Phụ thuộc chính (Key Dependencies)

### Backend (Python 3.11+)

| Package | Mục đích | Phase |
|---------|----------|-------|
| fastapi | REST API + WebSocket server | 1 |
| uvicorn | ASGI server | 1 |
| pydantic | Data validation | 1 |
| openai | OpenAI API SDK | 1 |
| anthropic | Claude API SDK | 1 |
| google-generativeai | Gemini API SDK | 1 |
| ollama | Ollama local SDK | 1 |
| langgraph | Agent orchestration | 2 |
| langchain-core | Tool + prompt abstractions | 2 |
| playwright | Browser automation | 2 |
| duckduckgo-search | Fallback web search | 2 |
| mss | Screenshot capture | 2 |
| Pillow | Image processing | 2 |
| chromadb | Vector database | 6 |
| sentence-transformers | Local embeddings | 6 |
| pytest | Testing | 1 |

### Frontend (Node.js 20+)

| Package | Mục đích | Phase |
|---------|----------|-------|
| react | UI framework | 3 |
| vite | Build tool | 3 |
| tailwindcss | Styling | 3 |
| axios | HTTP client | 3 |
| i18next | Internationalization | 3 |
| react-markdown | Markdown rendering | 3 |
| framer-motion | Animations | 3 |
| lucide-react | Icons | 3 |

---

## 4. Ràng buộc và Giới hạn (Constraints)

- **Single-user**: Chạy local, không cần auth
- **API Key required**: Cần ít nhất 1 LLM provider API key
- **Playwright install**: Cần chạy `playwright install` khi setup lần đầu
- **Port usage**: Backend 8000, Frontend 5173
- **OS support**: Windows (primary), macOS/Linux (secondary)
