"""FastAPI application entry point for JARVIS AI Assistant."""

# Force Windows to use ProactorEventLoop BEFORE any other import touches asyncio.
# Default on Python 3.13 is Proactor, but chromadb/sentence-transformers and
# uvicorn's reloader sometimes install a Selector policy during their own
# imports — SelectorEventLoop on Windows does NOT support subprocess operations,
# which caused shell_exec / code_runner to raise NotImplementedError at runtime.
import sys as _sys
if _sys.platform == "win32":
    import asyncio as _asyncio
    _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())

import logging
import logging.config
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# Persistent log file — rotates at 5 MB, keeps last 5 rotated backups.
# Lives under backend/logs so it survives across requests and is findable.
# Each server start TRUNCATES jarvis.log (fresh session) — backups .1-.5 stay
# intact so the last 5 sessions' logs remain available if needed.
# (RotatingFileHandler forces mode='a' internally when maxBytes>0, so we
#  can't rely on mode='w' — truncate before dictConfig runs.)
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "jarvis.log"
try:
    _LOG_FILE.write_text("", encoding="utf-8")
except OSError:
    # File locked by another process — handler will append; non-fatal.
    pass
from app.db.connection import init_db
from app.db.migrate_json import migrate_json_if_needed
from app.services.email_sync import start_scheduler, stop_scheduler
from app.routers.agent import router as agent_router
from app.routers.chat import router as chat_router
from app.routers.documents import router as documents_router
from app.routers.graph import router as graph_router
from app.routers.vault import router as vault_router
from app.routers.usage import router as usage_router
from app.routers.attachments import router as attachments_router
from app.routers.cvs import router as cvs_router
from app.routers.email_accounts import router as email_accounts_router
from app.routers.files import router as files_router
from app.routers.jobs import router as jobs_router
from app.routers.profile import router as profile_router
from app.routers.tts import router as tts_router

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

_LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(_LOG_FILE),
            "maxBytes": 5 * 1024 * 1024,   # 5 MB per file
            "backupCount": 5,               # keep last 5 rotations
            "encoding": "utf-8",
            "delay": True,                  # open on first write, not at config time
            # File is truncated once at process startup above — fresh session each run.
        },
    },
    # Mute verbose third-party libraries even when DEBUG is on for app code.
    # Without these overrides, a single embedding model load produces ~250 lines
    # of httpcore/filelock byte-level I/O events that swamp useful app logs.
    "loggers": {
        "httpcore": {"level": "WARNING"},
        "httpx": {"level": "WARNING"},
        "filelock": {"level": "WARNING"},
        "urllib3": {"level": "WARNING"},
        "sentence_transformers": {"level": "INFO"},
        "chromadb": {"level": "INFO"},
        "unstructured": {"level": "INFO"},
    },
    "root": {
        "level": "DEBUG" if settings.debug else "INFO",
        "handlers": ["console", "file"],
    },
}

logging.config.dictConfig(_LOGGING_CONFIG)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

def _check_api_keys() -> list[str]:
    """Return list of providers that have an API key configured (Ollama always)."""
    available: list[str] = []
    if settings.openai_api_key:
        available.append("openai")
    if settings.google_api_key:
        available.append("gemini")
    if settings.anthropic_api_key:
        available.append("claude")
    available.append("ollama")  # local, no key required
    return available


def _check_chromadb() -> bool:
    """Verify ChromaDB persist dir is writable. Non-fatal — logs warning only."""
    try:
        from pathlib import Path  # noqa: PLC0415

        persist_path = Path(settings.chroma_persist_dir)
        persist_path.mkdir(parents=True, exist_ok=True)
        probe = persist_path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception as exc:  # broad: any FS error is non-fatal at startup
        logger.warning(
            "ChromaDB persist dir not writable (%s): %s",
            settings.chroma_persist_dir,
            exc,
        )
        return False


def _check_playwright() -> bool:
    """Verify Playwright is importable (browser binary checked lazily on first use)."""
    try:
        from playwright.async_api import async_playwright  # noqa: F401, PLC0415
        return True
    except ImportError as exc:
        logger.warning(
            "Playwright not importable: %s — run `playwright install chromium`",
            exc,
        )
        return False


def _preload_ollama_model_bg() -> None:
    """Background thread: load the wikilink model into VRAM with keep_alive=-1.

    Runs in a daemon thread so the app starts serving immediately without
    waiting 5-10s for model cold-start. The model stays in VRAM until
    shutdown calls _unload_ollama_model().
    """
    if settings.wikilink_provider != "ollama":
        return
    model = settings.wikilink_model
    logger.info("Ollama preload starting in background — model '%s' ...", model)

    def _do_preload():
        try:
            import httpx  # noqa: PLC0415
            resp = httpx.post(
                f"{settings.ollama_base_url}/api/generate",
                json={"model": model, "prompt": "hi", "keep_alive": -1},
                timeout=120.0,
            )
            if resp.status_code == 200:
                logger.info("Ollama model '%s' preloaded into VRAM (keep_alive=-1)", model)
            else:
                logger.warning("Ollama preload returned %d: %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.warning("Could not preload Ollama model '%s': %s", model, exc)

    import threading  # noqa: PLC0415
    t = threading.Thread(target=_do_preload, daemon=True)
    t.start()


def _unload_ollama_model() -> None:
    """Unload the wikilink model from VRAM on app shutdown."""
    if settings.wikilink_provider != "ollama":
        return
    model = settings.wikilink_model
    try:
        import httpx  # noqa: PLC0415
        resp = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json={"model": model, "prompt": "", "keep_alive": 0},
            timeout=10.0,
        )
        if resp.status_code == 200:
            logger.info("Ollama model '%s' unloaded from VRAM", model)
    except Exception as exc:
        logger.warning("Could not unload Ollama model '%s': %s", model, exc)


def _preload_vieneu_tts_bg() -> None:
    """Background thread: download VieNeu-TTS GGUF model + init engine.

    Runs as a daemon thread so the app starts serving immediately.
    First run downloads ~200 MB from HuggingFace.
    """
    def _do_preload():
        try:
            from app.services.vieneu_tts import get_tts
            get_tts()
        except Exception as exc:
            logger.warning("VieNeu-TTS preload failed (non-fatal): %s", exc)

    import threading
    t = threading.Thread(target=_do_preload, daemon=True)
    t.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log startup info and run health checks before serving traffic."""
    logger.info(
        "JARVIS AI Assistant starting — host=%s port=%s debug=%s",
        settings.host,
        settings.port,
        settings.debug,
    )
    logger.info("Log file: %s (rotates at 5 MB, keeps 5 backups)", _LOG_FILE)
    logger.info("CORS origins: %s", settings.cors_origins)
    logger.info(
        "Default provider: %s  model: %s",
        settings.default_provider,
        settings.default_model,
    )

    # ── Health checks ────────────────────────────────────────────
    available_providers = _check_api_keys()
    if available_providers == ["ollama"]:
        logger.warning(
            "No cloud LLM API keys configured. Only Ollama (local) will work. "
            "Set OPENAI_API_KEY / GOOGLE_API_KEY / ANTHROPIC_API_KEY in backend/.env."
        )
    else:
        logger.info("LLM providers ready: %s", ", ".join(available_providers))

    if _check_chromadb():
        logger.info("ChromaDB persist dir OK: %s", settings.chroma_persist_dir)

    # Initialise SQLite schema + migrate the legacy documents_metadata.json if present.
    try:
        await init_db()
        migration = await migrate_json_if_needed()
        if migration.get("status") == "migrated":
            logger.info(
                "Migrated JSON metadata → SQLite: %d docs, %d wikilinks",
                migration.get("docs", 0),
                migration.get("links", 0),
            )
    except Exception as exc:  # DB is required — log clearly if it fails.
        logger.error("SQLite init/migration failed: %s", exc)

    _check_playwright()

    # Preload Ollama wikilink model in background — app serves immediately.
    _preload_ollama_model_bg()

    # Preload VieNeu-TTS model in background (downloads GGUF on first run).
    _preload_vieneu_tts_bg()

    # Start APScheduler for email sync (Phase 2) + job refresh (Phase 3).
    try:
        start_scheduler()
    except Exception as exc:
        logger.warning("Scheduler start failed (non-fatal): %s", exc)
    # ─────────────────────────────────────────────────────────────

    yield

    # ── Shutdown: stop scheduler + unload Ollama model to free VRAM ──
    stop_scheduler()
    _unload_ollama_model()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="JARVIS AI Assistant",
    version="0.1.0",
    description="An AI assistant that can execute real actions: browse the web, search the internet, and interact with the computer.",
    lifespan=lifespan,
)

# CORS — allow origins configured in settings (typically localhost:5173 + localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat_router)
app.include_router(agent_router)
app.include_router(documents_router)
app.include_router(graph_router)
app.include_router(vault_router)
app.include_router(usage_router)
app.include_router(attachments_router)
app.include_router(email_accounts_router)
app.include_router(profile_router)
app.include_router(jobs_router)
app.include_router(cvs_router)
app.include_router(files_router)
app.include_router(tts_router)


# ---------------------------------------------------------------------------
# Utility endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root() -> dict:
    """Root endpoint — quick service identification."""
    return {
        "name": "JARVIS AI Assistant",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health() -> dict:
    """Health check endpoint used by load balancers and monitoring tools."""
    return {"status": "healthy"}
