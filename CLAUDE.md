# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

JARVIS AI Assistant — an **action-capable** AI agent (not just a chatbot). It uses a LangGraph ReAct loop to decide which tool to call, then executes real operations: web search, headless browser navigation, screenshot, desktop control (PyAutoGUI), file I/O inside a sandbox, whitelisted app launch, RAG search over uploaded documents, and an Obsidian-style knowledge graph of the user's document corpus.

Status: 8 phases complete. See `task.md` and `implementation_plan.md` for scope, `PHASE_8_SUMMARY.md` for the latest (Knowledge Graph).

## Architecture (big picture)

The agent is built around three layers that must be understood together:

**1. LangGraph ReAct brain (`backend/app/agent/brain.py`)**

- `_build_llm(provider, model)` is the real "factory" — a function that returns the right `ChatOpenAI` / `ChatGoogleGenerativeAI` / `ChatAnthropic` / Ollama-via-OpenAI client. There is no `LLMFactory` class; extend the provider set by editing this function.
- `create_agent_brain()` wraps the LLM with `langgraph.prebuilt.create_react_agent`, binding a `JARVIS_SYSTEM_PROMPT` (templated with today's date) and a list of LangChain-compatible tools.
- `run_agent()` returns `{response, actions, messages}`. Content can arrive as plain string **or as a list of content blocks (Gemini 2.5)** — the extractor in `brain.py` must iterate `content` lists and pull only `{"type": "text", "text": ...}` blocks. Any new provider added must preserve this handling.
- `stream_agent()` yields typed events (`action` / `action_result` / `text` / `done`) for `/ws/agent` and the SSE routes.
- Default `recursion_limit=10` — both a safety bound and a soft UX contract (ActionViewer assumes at most ~10 steps).

**2. Tool Registry + Safety Guard (`backend/app/tools/`)**

- Every tool subclasses `BaseTool` (`tools/base.py`) with class attributes `name`, `description`, `parameters` (JSON Schema) and an async `execute(**kwargs) -> ToolResult`. Tools **must not raise** — failures return `ToolResult(success=False, error=...)` so the ReAct loop keeps going.
- `ToolRegistry.to_langchain_tools()` (`tools/registry.py`) dynamically builds a Pydantic `args_schema` from each tool's JSON Schema and wraps it in a `StructuredTool`. Both async (`coroutine=_arun`) and sync (`func=_run` via `asyncio.run`) paths exist; LangGraph uses the async path.
- `create_default_registry()` (`tools/__init__.py`) is the single source of truth for the 8 shipped tools: `web_search`, `web_browser`, `screenshot`, `desktop_control`, `browser_control`, `file_manager`, `app_launcher`, `rag_search`.
- `SafetyGuard` (`tools/safety.py`) classifies actions into 4 levels — `AUTO` (read/search/screenshot), `NOTIFY` (open app / navigate), `CONFIRM` (writes), `BLOCK` (delete, system paths, non-whitelisted apps). New tools that touch the FS, OS, or user's session MUST route through `SafetyGuard` before executing.

**3. RAG + Knowledge Graph pipeline (`backend/app/rag/` + `backend/app/graph/`)**

- RAG: `unstructured.partition` → chunking → `sentence-transformers/all-MiniLM-L6-v2` embeddings → ChromaDB `PersistentClient` under `./chroma_data`. One ChromaDB collection stores all docs; `metadata.doc_id` tags each chunk.
- Knowledge Graph (Phase 8, `graph/builder.py`): loads `uploads/documents_metadata.json`, aggregates per-doc chunk embeddings into a document-level mean vector, and emits an edge for every pair whose cosine similarity exceeds the threshold. O(n²) — designed for ≤1 000 docs; above that, switch to ChromaDB HNSW top-K.
- `graph/cache.py` memoises the last built graph so repeated `/api/graph` calls stay cheap; invalidate whenever documents change.
- Frontend renders the graph with `react-force-graph-2d` (pan/zoom/drag, node click → `GraphDetailPanel`).

**Frontend (`frontend/src/`)**

- React 19 + Vite 8 + **Bootstrap 5 / react-bootstrap** (not Tailwind). ChatGPT-style layout: full-width message rows, sticky input capped at `max-w-768px`.
- State lives in hooks: `useAgent` (REST + SSE), `useWebSocket` (`/ws/agent`), `useGraph`, `useSettings`, `useVoice`.
- Voice I/O is **browser-native** — `SpeechRecognition` for STT and `SpeechSynthesis` for TTS. There is no server-side TTS route.
- i18n via `react-i18next` with `en.json` / `vi.json`; language toggled in the Settings panel.

## Development commands

### Backend (Python 3.11+, `backend/` cwd)

```bash
python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate      # Linux/macOS
pip install -r requirements.txt
playwright install chromium      # MUST run after pip install
cp .env.example .env             # fill in API keys
uvicorn app.main:app --reload --port 8000
```

### Frontend (`frontend/` cwd)

```bash
npm install
npm run dev         # http://localhost:5173
npm run build       # production build
npm run lint        # ESLint 9 (flat config)
npm run test:e2e    # Playwright — BACKEND must already be running on :8000
npm run test:e2e:ui # Playwright UI mode
```

Playwright auto-starts the Vite dev server but **does not** start the backend — the E2E tests assume `http://localhost:8000` is live (see `frontend/playwright.config.js` comment for the rationale).

### Tests (backend, `backend/` cwd)

```bash
pytest -v                                     # full suite (async mode auto-enabled)
pytest tests/test_agent.py -v                 # single file
pytest tests/test_graph.py::TestGraphBuilder -v     # single class
pytest -k "safety and block" -v               # filter by name
pytest --cov=app --cov-report=term-missing    # coverage (needs pytest-cov)
```

`conftest.py` provides a `mock_settings` fixture that patches `app.core.config.settings` with fake API keys — use it for any test that exercises the router layer without hitting real providers.

### Full-stack shortcuts (Windows)

```bat
start.bat           :: venv + deps + playwright install + launch backend & frontend
stop.bat            :: kill both dev servers
restart_backend.bat :: restart uvicorn only
```

## Configuration (`backend/.env`)

```env
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...
# OLLAMA_BASE_URL=http://localhost:11434     # optional, default

DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-4o
# CHROMA_PERSIST_DIR=./chroma_data           # optional, default
# UPLOAD_DIR=./uploads                       # optional, default
```

At least one cloud key **or** a running Ollama is required. The provider is switchable at runtime from the frontend Settings panel — `/api/agent/execute` takes `provider` + `model` in the request body.

## Provider caveats (stable gotchas, not derivable from code)

- **Gemini** (Google safety filters) rejects `desktop_control`, `browser_control`, `file_manager`, `app_launcher` in practice — tests assume only `web_search` and `rag_search` work reliably with Gemini. Do not add Gemini-specific tool tests for the blocked set.
- **Gemini 2.5** returns assistant content as `list[{"type": "text", "text": ...}, ...]` instead of a plain string. Both `run_agent` and `stream_agent` handle this; keep it that way when touching the message-extraction loop.
- **Ollama** is wired through `ChatOpenAI` against Ollama's OpenAI-compatible endpoint (`base_url + "/v1"`, api_key `"ollama"`). Do not add a separate `ChatOllama` path.
- **Playwright** browser binary is not installed by `pip install` — the `_check_playwright()` health check only verifies the import. First run of `web_browser` / `browser_control` will fail until `playwright install chromium` has been executed.

## Project-specific rules (override generic defaults)

- **Never code without approval.** The repo follows `AI_AGENT_PROTOCOL.md`: `task.md` breakdown → `implementation_plan.md` → **wait for user approval** → execute → mark `[x]` → dual-pass review → append any issue to `docs/known_issues_and_learnings.md`.
- **Docs must move with code.** Any change to tools, routes, or the agent contract must update the matching section in `docs/technical_reference.md` + `task.md` + `README.md` in the same commit.
- **Code comments: English. Planning docs: Vietnamese. UI copy: bilingual via `i18n/`.** Do not commit Vietnamese identifiers or comments in source files.
- **Async all the way down.** No blocking I/O in request handlers or tools. Heavy singletons (Playwright browser, embedding model) are initialised once and reused.
- **Immutability.** Agent state and tool args are never mutated in place; build a new dict/object instead.
- **Line length 120** (`ruff` config in `backend/pyproject.toml`), not 80 or 400. Files above ~400 lines should be split by responsibility.

## Git workflow

Branching: `main` ← `develop` ← `feature/*`. PR required for every merge into `develop` and `main`. Conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `perf:`, `ci:`).

## Common pitfalls

- **`playwright install chromium` missing** — `web_browser` / `browser_control` tools 500 on first call. Re-run it in the active venv.
- **CORS** — backend allows `http://localhost:5173` and `http://localhost:3000` by default (`settings.cors_origins`). Add any new origin here, not in per-router middleware.
- **WebSocket drops** — frontend `useWebSocket` must reconnect with exponential backoff; the backend does not retry for you.
- **Tool timeout** — tools have an implicit ~30 s budget. Long-running browser flows should chunk work across multiple tool calls rather than hold the coroutine.
- **Graph staleness** — after upload/delete in the documents panel, invalidate the graph cache (`graph/cache.py`) or the Knowledge Graph panel will show the previous build.
