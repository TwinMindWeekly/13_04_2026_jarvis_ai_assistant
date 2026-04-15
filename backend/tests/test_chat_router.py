"""Tests for the chat API router — /api/chat, /api/providers, /api/providers/test."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.schemas import ChatResponse, ProviderName, StreamChunk, TokenUsage


# ---------------------------------------------------------------------------
# Utility endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_root_endpoint():
    """GET / returns 200 with service name and version."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "JARVIS AI Assistant"
    assert "version" in body


@pytest.mark.asyncio
async def test_health_endpoint():
    """GET /health returns 200 with healthy status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# Providers list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_providers(mock_settings):
    """GET /api/providers returns a list of ProviderInfo objects."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/providers")
    assert response.status_code == 200
    providers = response.json()
    assert isinstance(providers, list)
    assert len(providers) > 0
    # Each item must have the expected fields
    for item in providers:
        assert "name" in item
        assert "available" in item
        assert "models" in item
        assert isinstance(item["models"], list)
    # All four known providers are present
    names = {p["name"] for p in providers}
    assert {"openai", "gemini", "claude", "ollama"}.issubset(names)


# ---------------------------------------------------------------------------
# Non-streaming chat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_non_streaming(mock_settings, test_messages):
    """POST /api/chat with stream=False returns a ChatResponse JSON body."""
    fake_response = ChatResponse(
        content="Hello from mock!",
        provider="openai",
        model="gpt-4o",
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )

    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock(return_value=fake_response)

    with patch("app.routers.chat.LLMFactory.create", return_value=mock_provider):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/chat",
                json={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "provider": "openai",
                    "model": "gpt-4o",
                    "stream": False,
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Hello from mock!"
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# Streaming chat (SSE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_streaming(mock_settings):
    """POST /api/chat with stream=True returns SSE chunks from the provider."""
    chunks = [
        StreamChunk(content="Hello", done=False),
        StreamChunk(content=" world", done=False),
        StreamChunk(content="", done=True),
    ]

    async def fake_stream(*args, **kwargs):
        for chunk in chunks:
            yield chunk

    mock_provider = MagicMock()
    mock_provider.chat_stream = fake_stream

    with patch("app.routers.chat.LLMFactory.create", return_value=mock_provider):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/chat",
                json={
                    "messages": [{"role": "user", "content": "Hi"}],
                    "provider": "openai",
                    "model": "gpt-4o",
                    "stream": True,
                },
            )

    assert response.status_code == 200
    # SSE responses carry text/event-stream content type
    assert "text/event-stream" in response.headers.get("content-type", "")
    # Verify the raw body contains at least one SSE data line
    raw = response.text
    assert "data:" in raw
    # Parse the first non-empty data line and confirm it is valid JSON
    data_lines = [
        line[len("data:"):].strip()
        for line in raw.splitlines()
        if line.startswith("data:")
    ]
    assert len(data_lines) > 0
    first = json.loads(data_lines[0])
    assert "content" in first
    assert "done" in first


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_invalid_provider():
    """POST /api/chat with an unsupported provider value returns 422 (Pydantic validation)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Hi"}],
                "provider": "totally_invalid_provider",
                "model": "some-model",
                "stream": False,
            },
        )
    # FastAPI/Pydantic rejects unknown enum values with 422 Unprocessable Entity
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_empty_messages_rejected():
    """POST /api/chat with an empty messages list returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={
                "messages": [],
                "provider": "openai",
                "model": "gpt-4o",
                "stream": False,
            },
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Provider test endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_test_endpoint(mock_settings):
    """POST /api/providers/test returns success=True when test_connection passes."""
    mock_provider = MagicMock()
    mock_provider.test_connection = AsyncMock(return_value=True)

    with patch("app.routers.chat.LLMFactory.create", return_value=mock_provider):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/providers/test",
                json={"provider": "openai", "api_key": "test-key-openai"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["provider"] == "openai"
    assert "latency_ms" in body


@pytest.mark.asyncio
async def test_provider_test_endpoint_failure(mock_settings):
    """POST /api/providers/test returns success=False when test_connection fails."""
    mock_provider = MagicMock()
    mock_provider.test_connection = AsyncMock(return_value=False)

    with patch("app.routers.chat.LLMFactory.create", return_value=mock_provider):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/providers/test",
                json={"provider": "openai", "api_key": "bad-key"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
