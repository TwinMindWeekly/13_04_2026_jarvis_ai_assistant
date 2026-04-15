"""Chat router — exposes /api/chat, /api/providers, /api/providers/test."""

import json
import logging
import time
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ProviderInfo,
    ProviderName,
    ProviderTestRequest,
    ProviderTestResponse,
    StreamChunk,
)
from app.services.llm_factory import LLMFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Default models advertised for each provider
_PROVIDER_MODELS: dict[str, list[str]] = {
    ProviderName.OPENAI: ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    ProviderName.GEMINI: ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    ProviderName.CLAUDE: ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
    ProviderName.OLLAMA: ["llama3.2", "mistral", "gemma2"],
}


def _resolve_api_key(provider: str) -> str:
    """Return the configured API key for *provider* from settings."""
    key_map: dict[str, str] = {
        ProviderName.OPENAI: settings.openai_api_key,
        ProviderName.GEMINI: settings.google_api_key,
        ProviderName.CLAUDE: settings.anthropic_api_key,
        ProviderName.OLLAMA: "",
    }
    return key_map.get(provider, "")


@router.post("/chat")
async def chat(request: ChatRequest):
    """Main chat endpoint — supports both blocking and SSE streaming responses."""
    api_key = _resolve_api_key(request.provider)
    base_url = settings.ollama_base_url if request.provider == ProviderName.OLLAMA else ""

    try:
        provider = LLMFactory.create(
            provider=request.provider,
            model=request.model,
            api_key=api_key,
            base_url=base_url,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error creating provider '%s'", request.provider)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if request.stream:
        # Return a Server-Sent Events streaming response
        async def event_generator() -> AsyncIterator[dict]:
            try:
                async for chunk in provider.chat_stream(
                    messages=request.messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                ):
                    yield {"data": json.dumps(chunk.model_dump())}
            except HTTPException:
                raise
            except Exception as exc:
                logger.exception("Streaming error for provider '%s'", request.provider)
                error_chunk = StreamChunk(content=str(exc), done=True)
                yield {"data": json.dumps(error_chunk.model_dump())}

        return EventSourceResponse(event_generator())

    # Blocking (non-streaming) response
    try:
        response: ChatResponse = await provider.chat(
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chat error for provider '%s'", request.provider)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers() -> list[ProviderInfo]:
    """Return all supported providers with availability and default model list."""
    availability: dict[str, bool] = {
        ProviderName.OPENAI: bool(settings.openai_api_key),
        ProviderName.GEMINI: bool(settings.google_api_key),
        ProviderName.CLAUDE: bool(settings.anthropic_api_key),
        # Ollama is always considered available (local, no key required)
        ProviderName.OLLAMA: True,
    }

    return [
        ProviderInfo(
            name=provider,
            available=availability[provider],
            models=models,
        )
        for provider, models in _PROVIDER_MODELS.items()
    ]


@router.post("/providers/test", response_model=ProviderTestResponse)
async def test_provider(request: ProviderTestRequest) -> ProviderTestResponse:
    """Test connectivity for a given provider and return latency in milliseconds."""
    # Prefer the key from the request body; fall back to settings
    api_key = request.api_key if request.api_key else _resolve_api_key(request.provider)
    base_url = settings.ollama_base_url if request.provider == ProviderName.OLLAMA else ""

    try:
        provider = LLMFactory.create(
            provider=request.provider,
            model="",  # test_connection does not require a model
            api_key=api_key,
            base_url=base_url,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error creating provider '%s' for test", request.provider)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    start = time.perf_counter()
    try:
        success = await provider.test_connection()
        latency_ms = (time.perf_counter() - start) * 1000
        message = "Connection successful" if success else "Connection failed"
    except HTTPException:
        raise
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.exception("test_connection failed for provider '%s'", request.provider)
        return ProviderTestResponse(
            provider=request.provider,
            success=False,
            message=str(exc),
            latency_ms=round(latency_ms, 2),
        )

    return ProviderTestResponse(
        provider=request.provider,
        success=success,
        message=message,
        latency_ms=round(latency_ms, 2),
    )
