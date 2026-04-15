# CLAUDE.md — JARVIS AI Assistant Project Context

## What is this?

An AI assistant that goes beyond chatbots — it can **execute real actions**: browse the web, search the internet, take screenshots, and interact with the computer on behalf of the user. Inspired by JARVIS (Iron Man). Built with FastAPI + React + LangGraph.

## Architecture

- **Backend**: FastAPI (REST + WebSocket), async-first
- **Agent Brain**: LangGraph ReAct loop (Think → Act → Observe → Loop)
- **LLM Providers**: OpenAI, Gemini, Claude, Ollama — switchable via Factory Pattern
- **Tools**: Playwright (browser), Google/Bing/DuckDuckGo (search), mss (screenshot), ChromaDB (RAG)
- **Frontend**: React 19 + Vite + Tailwind CSS + glassmorphism UI
- **Voice**: Web Speech API (STT) + OpenAI TTS / Browser native (TTS)
- **Protocol**: Vietnamese-language AI_AGENT_PROTOCOL.md enterprise guidelines

## Key Directory Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── core/                # Config, exceptions
│   ├── models/              # Pydantic schemas
│   ├── services/            # LLM Factory
│   ├── tools/               # Tool registry + individual tools
│   ├── agent/               # LangGraph agent brain
│   └── routers/             # API endpoints
├── tests/
└── requirements.txt

frontend/
├── src/
│   ├── components/          # ChatArea, ActionViewer, Settings
│   ├── hooks/               # useWebSocket, useAgent
│   ├── services/            # API client
│   └── i18n/                # en.json, vi.json
└── package.json
```

## Important Patterns

- **LLM Factory Pattern**: `LLMFactory.create(provider, model, api_key)` → returns provider-specific client. Each provider normalizes tool/function calling format internally.
- **Tool Registry**: All tools implement `BaseTool` interface with `name`, `description`, `parameters` (JSON Schema), and `async execute(**kwargs) → ToolResult`.
- **Agent ReAct Loop**: LangGraph StateGraph with max 10 tool calls per request to prevent infinite loops. Each step logged to `action_history` for frontend ActionViewer.
- **Safety Layer**: 4 levels — auto-approve (read), notify (navigate), confirm (write), block (delete). Applied to all computer_use and file_manager actions.
- **Streaming**: All LLM responses support streaming via SSE (REST) or WebSocket. Agent action updates streamed in real-time.
- **Singleton heavy resources**: Playwright browser instance, embedding models — init once, reuse across requests.

## Development Commands

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev  # Port 5173

# Tests
cd backend && pytest -v
cd frontend && npm test
```

## Config

All secrets via `.env` file in `backend/`. Provider switchable at runtime from frontend Settings panel.

```env
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-4o
```

## Coding Rules

- **Language**: Code comments in English, user-facing text bilingual (vi/en via i18n), planning docs in Vietnamese
- **Async**: All backend I/O must be async/await. No blocking calls in request handlers.
- **Immutability**: Create new objects, never mutate. Agent state is immutable between steps.
- **Error handling**: Every tool wraps execution in try/except, returns `ToolResult(success=False, error=...)` on failure. Never crash the agent loop.
- **No hardcoded secrets**: All API keys from environment variables only.
- **File size**: Max 400 lines per file, extract when exceeding.
- **Documentation sync**: Any code change MUST update relevant docs (README, technical_reference, task.md).

## AI Agent Protocol

This project follows `AI_AGENT_PROTOCOL.md` strictly:
1. Break down → `task.md`
2. Plan → `implementation_plan.md`
3. Ask approval → **NEVER code without user approval**
4. Execute → mark `[x]` in `task.md`
5. Review → dual-pass before commit
6. Learn → log issues in `docs/known_issues_and_learnings.md`

## Git Workflow

- **Branching**: `main` (production) ← `develop` (integration) ← `feature/*` (work)
- **Commits**: Conventional commits — `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- **PR required**: Feature → develop, develop → main via Pull Request

## Common Pitfalls

- **Playwright browser not installed**: Run `playwright install chromium` after pip install
- **Provider rate limits**: All providers have retry logic with exponential backoff. If persistent, switch provider.
- **WebSocket disconnect**: Frontend must handle reconnection gracefully with exponential backoff.
- **Tool timeout**: All tools have 30s timeout. Long-running browser actions may need adjustment.
- **CORS**: Backend must allow `http://localhost:5173` in CORS origins during development.
