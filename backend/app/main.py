"""FastAPI application entry point for JARVIS AI Assistant."""

import logging
import logging.config

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.agent import router as agent_router
from app.routers.chat import router as chat_router
from app.routers.documents import router as documents_router
from app.routers.graph import router as graph_router
from app.routers.vault import router as vault_router
from app.routers.usage import router as usage_router
from app.routers.attachments import router as attachments_router

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
        "handlers": ["console"],
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log startup info and run health checks before serving traffic."""
    logger.info(
        "JARVIS AI Assistant starting — host=%s port=%s debug=%s",
        settings.host,
        settings.port,
        settings.debug,
    )
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

    _check_playwright()

    # Preload Ollama wikilink model in background — app serves immediately.
    _preload_ollama_model_bg()
    # ─────────────────────────────────────────────────────────────

    yield

    # ── Shutdown: unload Ollama model to free VRAM ──────────────
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
