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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log startup information once the server is ready."""
    logger.info(
        "JARVIS AI Assistant starting — host=%s port=%s debug=%s",
        settings.host,
        settings.port,
        settings.debug,
    )
    logger.info("CORS origins: %s", settings.cors_origins)
    logger.info("Default provider: %s  model: %s", settings.default_provider, settings.default_model)
    yield


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
