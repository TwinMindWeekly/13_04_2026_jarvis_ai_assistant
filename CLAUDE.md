# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

JARVIS AI Assistant — an **action-capable** AI agent (not just a chatbot). It uses a LangGraph ReAct loop to decide which tool to call, then executes real operations: web search, headless browser navigation, screenshot, desktop control (PyAutoGUI), file I/O inside a sandbox, whitelisted app launch, RAG search over uploaded documents, Obsidian-style knowledge graph with wikilink-based document relationships, SQLite-backed document metadata queries, shell commands, clipboard, OS notifications, multi-account email (IMAP/SMTP with FTS5 cache), image generation (DALL-E 3), code execution (Python/JS/Godot), job search across 6 sources, and a skill system with auto-loaded .md skills.

Status: Phases 1–18 complete (17 tools, 6 LLM providers). Phase 11 (Provider Usage Dashboard) deferred. See `task.md` for scope.

## Architecture (big picture)

**1. LangGraph ReAct brain (`backend/app/agent/brain.py`)**

- `_build_llm(provider, model)` — returns the right LangChain chat model for 6 providers: `openai`, `gemini`, `claude`, `groq`, `sambanova`, `ollama`. No `LLMFactory` class; extend the provider set by editing this function.
- `build_llm_with_fallback(provider, model)` — when `provider="auto"`, tries a chain in order: groq → gemini → sambanova → openai → claude → ollama. Skips any provider missing an API key. Runtime quota errors (429, 503) also trigger fallback in `routers/agent.py`.
- `create_agent_brain(provider, model, tools, language, user_message)` wraps the LLM with `langgraph.prebuilt.create_react_agent`, binding `JARVIS_SYSTEM_PROMPT` (from `agent/prompts.py`, templated with today's date and `{language}`) and a list of LangChain-compatible tools. Injects matched skill content via `skill_loader.get_prompt_injection(user_message)`. Returns `(brain, actual_provider, actual_model)`.
- `run_agent()` returns `{response, actions, messages}`. Content can arrive as plain string **or as a list of content blocks (Gemini 2.5)** — the extractor iterates `content` lists and pulls only `{"type": "text", "text": ...}` blocks. Any new provider must preserve this.
- `stream_agent()` yields typed events (`action` / `action_result` / `text` / `done`) for `/ws/agent` and SSE routes.
- Default `recursion_limit=10` — both a safety bound and a soft UX contract (ActionViewer assumes at most ~10 steps).

**2. Tool Registry + Safety Guard (`backend/app/tools/`)**

- Every tool subclasses `BaseTool` (`tools/base.py`) with `name`, `description`, `parameters` (JSON Schema) and async `execute(**kwargs) -> ToolResult`. Tools **must not raise** — failures return `ToolResult(success=False, error=...)`.
- `ToolRegistry.to_langchain_tools()` (`tools/registry.py`) dynamically builds a Pydantic `args_schema` from JSON Schema and wraps each in `StructuredTool`. LangGraph uses the async path.
- `create_default_registry()` (`tools/__init__.py`) — 15 tools: `web_search`, `web_browser`, `screenshot`, `desktop_control`, `browser_control`, `file_manager`, `app_launcher`, `rag_search`, `skill_manager`, `shell_exec`, `clipboard`, `system_notification`, `email`, `image_generator`, `code_runner`.
- `SafetyGuard` (`tools/safety.py`) — 4 levels: `AUTO` (read/search/screenshot/clipboard-read/email-read), `NOTIFY` (navigate/notification/image-gen/clipboard-write), `CONFIRM` (file-write/desktop-control/shell-exec/email-send/code-runner), `BLOCK` (rm -rf, format, mkfs, fork bomb, reg delete, taskkill, bcdedit). New tools touching FS/OS/session MUST route through SafetyGuard.

**2b. Skill System (`backend/app/skills/` + `backend/skills/`)**

- Skill files are `.md` with YAML frontmatter (`name`, `description`, `triggers`) in `backend/skills/`.
- `skills/loader.py` — `SkillLoader` singleton: parses all `.md` files on init, builds keyword triggers (from frontmatter `triggers` + common trigger dictionary), `match(user_message)` returns matching skills, `get_prompt_injection(user_message)` returns skill body text for system prompt injection.
- `skill_manager` tool — lets the agent `list`/`search` (GitHub API)/`install` (download .md)/`remove` skills at runtime.

**2c. SQLite persistence (`backend/app/db/`)** — Phase 16

- SQLAlchemy 2 async engine against `sqlite+aiosqlite:///./jarvis.db`. WAL + `foreign_keys=ON` enabled via event listener. Tables: `documents`, `wikilinks`, `email_accounts`, `email_messages` (+ FTS5 virtual table `email_messages_fts` with insert/delete/update triggers), `user_profile`, `jobs`, `saved_job_searches`.
- Bootstrap: `init_db()` (`Base.metadata.create_all` + FTS5 DDL) runs in lifespan; `migrate_json_if_needed()` imports legacy `uploads/documents_metadata.json` on first boot and renames it to `.migrated`.
- Service helpers live in `app/db/services/`: `documents.py` (CRUD + wikilink resolver), `email_accounts.py` (encrypted-password CRUD), `user_profile.py` (singleton row), `jobs.py` (saved searches + `refresh_jobs` / `refresh_from_profile_defaults`).
- Agent access to document metadata goes through the `doc_query` tool (`find_by_wikilink`, `find_backlinks`, `list_by_folder`, `list_all`, `get_metadata`, `read_doc`) — not through the prompt.

**2d. Multi-Gmail + Fernet secrets (`backend/app/services/secrets.py`, `email_client.py`, `email_sync.py`)** — Phase 17

- Passwords encrypted with `cryptography.Fernet`. Key lives in `settings.jarvis_secret_key`; if empty, `get_fernet()` auto-generates one and appends it to `backend/.env` with a loud warning. Losing the key = losing stored passwords.
- `EmailClient(credentials)` is bound to one `EmailAccount`; `make_client(acct)` builds a fresh client per call. New IMAP actions: `search_by_date`, `search_by_sender`, `search_important`, plus `search_cached` (FTS5 over the `email_messages` cache).
- `start_scheduler()` (APScheduler) runs `sync_all_accounts` every `email_sync_interval_minutes` (default 5) and a daily `jobs_refresh`. Started in the main lifespan.

**2e. Profile + Jobs (`backend/app/routers/{profile,jobs}.py`, `app/services/{cv_extractor,jobs_matcher,job_sources}/`)** — Phase 18

- `POST /api/profile/upload` parses the CV via `DocumentParser` → `cv_extractor.extract_profile_fields` (LLM JSON) → upserts `user_profile`. Frontend `ProfilePage` also lets the user edit skills/titles/locations/remote manually.
- 6 job sources live in `app/services/job_sources/`: `duckduckgo`, `topcv`, `itviec`, `vietnamworks`, `remoteok`, `weworkremotely`. Each exports `async def fetch(query, location, limit)` and **must swallow every network/parsing exception** so one flaky site can't break the daily refresh.
- `jobs_matcher.score_job(job, profile)` = Jaccard overlap of skills/titles tokens + small location/remote bonus → 0..1.
- Agent access via the `job_search` tool: `list_tracked`, `search`, `refresh`, `save`, `unsave`.

**3. RAG + Wikilink pipeline (`backend/app/rag/` + `backend/app/graph/`)**

- RAG: `unstructured.partition` → chunking → `sentence-transformers/all-MiniLM-L6-v2` embeddings → ChromaDB `PersistentClient` under `./chroma_data`.
- **Upload pipeline** (Phase 10): upload → `rag/md_converter.py` (MarkItDown) converts PDF/DOCX/PPTX/XLSX to Markdown → `rag/wikilink_generator.py` injects `[[wikilinks]]` via LLM (uses `WIKILINK_PROVIDER`, not the agent provider) → saved as `uploads/vault/{doc_id}.md` → chunks indexed in ChromaDB.
- **Knowledge Graph** (`graph/builder.py`): now **wikilink-only** — `graph/link_extractor.py` parses `[[Target]]` and `[[Target|Display]]` from vault Markdown, fuzzy-matches filenames, and emits edges. No more cosine similarity. O(n·k) where k = avg wikilinks/doc.
- `graph/cache.py` — JSON file cache keyed by MD5 of `(sorted_doc_ids, wikilink_count)`. Invalidates on document upload/delete.
- Vault API: `routers/vault.py` — `GET /api/vault/{doc_id}` (read), `PUT /api/vault/{doc_id}` (edit).

**4. Frontend (`frontend/src/`)**

- React 19 + Vite 8 + **Bootstrap 5 / react-bootstrap** (not Tailwind).
- Two view modes toggled via `viewMode` state in `App.jsx`:
  - **Chat view** — ChatGPT-style layout: `ChatArea`, `Sidebar` with doc tree (`SidebarDocTree` / `SidebarDocNode`), `ActionViewer`, `SettingsPanel`, `DocumentsPanel`.
  - **Graph view** (`GraphPage.jsx`) — Obsidian-style 3-panel layout: left panel (`GraphLeftPanel` — doc list + detail on node click), center (`GraphCanvas` — `react-force-graph-2d` with folder-based coloring, hover highlight, search/filter), right floating chat overlay using `ChatArea` with suggestion chips. A `MarkdownEditorPanel` opens on node select for inline vault editing with wikilink syntax highlighting.
- `ResizeHandle.jsx` — draggable panel resize for the split layout.
- `AttachmentPreview.jsx` — pill badges for attached files with char count and remove button.
- `ResizeHandle.jsx` — draggable panel resize for the split layout.
- State hooks: `useAgent` (REST + SSE, independent instance per page, supports `cancelRequest()` via AbortController), `useWebSocket` (`/ws/agent`), `useGraph`, `useSettings`, `useVoice`, `useDocTree`, `useAttachments` (file upload state management).
- Chat file upload: "+" button and drag-and-drop, max 5 MB, 43 extensions, ephemeral parse (not indexed to ChromaDB).
- Cancel request: square stop button replaces spinner during processing.
- Language toggle: EN/VI buttons in header, language passed to agent for response localization.
- Voice I/O is **browser-native** — `SpeechRecognition` for STT, `SpeechSynthesis` for TTS. No server-side TTS.
- i18n via `react-i18next` with `en.json` / `vi.json`; language toggled in header and Settings panel.

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

Playwright auto-starts the Vite dev server but **does not** start the backend — E2E tests assume `http://localhost:8000` is live.

### Tests (backend, `backend/` cwd)

```bash
pytest -v                                     # full suite (asyncio_mode = "auto")
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
# At least one cloud key OR a running Ollama is required
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
SAMBANOVA_API_KEY=...

# "auto" enables fallback chain: groq → gemini → sambanova → openai → claude → ollama
DEFAULT_PROVIDER=auto
DEFAULT_MODEL=                              # empty = auto-detect per provider

# Per-provider model selection (optional, has sensible defaults)
OPENAI_MODEL=gpt-4o-mini
GEMINI_MODEL=gemini-2.5-flash
CLAUDE_MODEL=claude-sonnet-4-5
GROQ_MODEL=llama-3.3-70b-versatile
SAMBANOVA_MODEL=Meta-Llama-3.1-8B-Instruct

# Proxy support (e.g. Antigravity Manager on port 8045)
# OPENAI_BASE_URL=http://localhost:8045/v1
# GEMINI_BASE_URL=http://localhost:8045/v1
# ANTHROPIC_BASE_URL=http://localhost:8045   # no /v1 for Anthropic

# Wikilink generation uses a separate provider (Ollama local recommended)
WIKILINK_PROVIDER=ollama
WIKILINK_MODEL=huihui_ai/llama3.2-abliterate:3b

# Email (optional — for email tool)
# IMAP_HOST=imap.gmail.com
# IMAP_PORT=993
# IMAP_USER=your@gmail.com
# IMAP_PASSWORD=your-app-password
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your@gmail.com
# SMTP_PASSWORD=your-app-password

# Code runner (optional)
# GODOT_PATH=                               # path to Godot executable

# OLLAMA_BASE_URL=http://localhost:11434    # optional, default
# SAMBANOVA_BASE_URL=https://api.sambanova.ai/v1  # optional, default
# CHROMA_PERSIST_DIR=./chroma_data          # optional, default
# UPLOAD_DIR=./uploads                      # optional, default

# SQLite + secrets (Phase 16/17)
# SQLITE_PATH=./jarvis.db                   # optional, default
# JARVIS_SECRET_KEY=                        # Fernet key for encrypting email passwords.
#                                           # Auto-generated on first boot and written back to .env
#                                           # with a loud warning — BACK THIS UP.
# EMAIL_SYNC_INTERVAL_MINUTES=5             # IMAP → email_messages cache (APScheduler)
# JOBS_REFRESH_INTERVAL_MINUTES=1440        # daily job source refresh
```

Provider is switchable at runtime from the frontend Settings panel — `/api/agent/execute` takes `provider` + `model` in the request body.

## Provider caveats

- **Auto-fallback** — `DEFAULT_PROVIDER=auto` tries providers in order by key availability. Runtime quota errors (429/503/"rate_limit"/"quota"/"token pool is empty") trigger retry with the next provider in `routers/agent.py`.
- **Proxy support** — `OPENAI_BASE_URL`, `GEMINI_BASE_URL`, `ANTHROPIC_BASE_URL` route through an OpenAI-compatible proxy (e.g. Antigravity Manager). Gemini proxy uses `ChatOpenAI` instead of `ChatGoogleGenerativeAI`. Anthropic proxy uses `anthropic_api_url` (no `/v1` suffix).
- **Per-provider models** — each provider has a configurable default model via env (`OPENAI_MODEL`, `GEMINI_MODEL`, `CLAUDE_MODEL`, `GROQ_MODEL`, `SAMBANOVA_MODEL`). Runtime override via Settings panel or request body.
- **Groq / SambaNova** — wired through `ChatOpenAI` with custom `base_url`, same as Ollama. Free tier limits: Groq 1000 req/day, SambaNova 200 req/day.
- **Gemini** safety filters reject `desktop_control`, `browser_control`, `file_manager`, `app_launcher` in practice — tests assume only `web_search` and `rag_search` work reliably with Gemini.
- **Gemini 2.5** returns assistant content as `list[{"type": "text", "text": ...}]` instead of a plain string. Both `run_agent` and `stream_agent` handle this; keep it that way.
- **Ollama** — wired through `ChatOpenAI` against `base_url + "/v1"`, api_key `"ollama"`. Do not add a separate `ChatOllama` path.
- **Split LLM config** — agent chat uses `DEFAULT_PROVIDER`; wikilink generation uses `WIKILINK_PROVIDER`/`WIKILINK_MODEL` (separate so wikilinks can use a cheap local model while chat uses a cloud model).
- **Playwright** browser binary is not installed by `pip install` — first run of `web_browser` / `browser_control` will fail until `playwright install chromium`.

## API routes (`backend/app/routers/`)

| Router | Key endpoints |
|--------|--------------|
| `agent.py` | `POST /api/agent/execute`, `WS /ws/agent`, `GET /api/providers` |
| `chat.py` | `POST /api/chat` (simple text-in/text-out, no tools) |
| `documents.py` | `POST /api/documents/upload`, `GET /api/documents`, `DELETE /api/documents/{id}` |
| `graph.py` | `GET /api/graph/data`, `GET /api/graph/stats`, `POST /api/graph/rebuild` |
| `vault.py` | `GET /api/vault/{doc_id}`, `PUT /api/vault/{doc_id}` |
| `attachments.py` | `POST /api/agent/upload-attachment` (ephemeral file parse for chat, 5MB/43 ext) |
| `files.py` | `GET /api/files/generated/{filename}` (serve DALL-E generated images) |
| `usage.py` | `GET /api/usage/` (provider usage stats) |
| `email_accounts.py` | `GET/POST/PATCH/DELETE /api/email-accounts`, `POST /api/email-accounts/{id}/test` |
| `profile.py` | `GET/PUT /api/profile`, `POST /api/profile/upload` (CV parse + LLM extract) |
| `jobs.py` | `GET /api/jobs`, `POST /api/jobs/refresh`, `POST/DELETE /api/jobs/{id}/save`, `GET/POST /api/jobs/saved-searches`, `DELETE /api/jobs/saved-searches/{id}` |

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
- **Graph staleness** — after upload/delete in the documents panel, the graph cache (`graph/cache.py`) should auto-invalidate. If it doesn't, `POST /api/graph/rebuild` forces a rebuild.
- **Wikilink pipeline requires LLM** — if no LLM key is available for `WIKILINK_PROVIDER`, the wikilink step is skipped and the graph shows only orphan nodes (no edges).
- **Vault files** — converted Markdown lives in `uploads/vault/{doc_id}.md`. Edits via `PUT /api/vault/{doc_id}` update this file; re-extracting wikilinks after edit is not yet automatic.
