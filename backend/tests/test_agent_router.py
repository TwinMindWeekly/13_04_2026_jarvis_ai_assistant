"""Tests for the agent API router: POST /api/agent/execute."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from app.main import app


# ---------------------------------------------------------------------------
# POST /api/agent/execute — success cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_execute_endpoint(mock_settings):
    """POST /api/agent/execute returns 200 with conversation_id, response, and actions."""
    with patch("app.routers.agent.create_default_registry") as mock_registry_factory, \
         patch("app.routers.agent.create_agent_brain") as mock_create_brain, \
         patch("app.routers.agent.run_agent") as mock_run:

        # Registry produces an empty LangChain tool list.
        mock_registry = MagicMock()
        mock_registry.to_langchain_tools.return_value = []
        mock_registry_factory.return_value = mock_registry

        mock_brain = MagicMock()
        mock_create_brain.return_value = mock_brain

        mock_run.return_value = AsyncMock(return_value={
            "response": "The weather is sunny",
            "actions": [
                {
                    "step": 1,
                    "tool": "web_search",
                    "input": {"query": "weather"},
                    "output": "Sunny skies",
                    "status": "completed",
                    "duration_ms": 100,
                }
            ],
            "messages": [],
        })
        # run_agent is async — make the mock awaitable directly
        mock_run.return_value = {
            "response": "The weather is sunny",
            "actions": [
                {
                    "step": 1,
                    "tool": "web_search",
                    "input": {"query": "weather"},
                    "output": "Sunny skies",
                    "status": "completed",
                    "duration_ms": 100,
                }
            ],
            "messages": [],
        }
        mock_run.side_effect = None
        mock_run.__class__ = AsyncMock
        # Simplest approach: make run_agent an AsyncMock
        mock_run_async = AsyncMock(return_value={
            "response": "The weather is sunny",
            "actions": [
                {
                    "step": 1,
                    "tool": "web_search",
                    "input": {"query": "weather"},
                    "output": "Sunny skies",
                    "status": "completed",
                    "duration_ms": 100,
                }
            ],
            "messages": [],
        })

        with patch("app.routers.agent.run_agent", mock_run_async):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/agent/execute",
                    json={
                        "message": "What is the weather?",
                        "provider": "openai",
                        "model": "gpt-4o",
                    },
                )

    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "The weather is sunny"
    assert len(data["actions"]) == 1
    assert data["actions"][0]["tool"] == "web_search"
    assert data["actions"][0]["output"] == "Sunny skies"
    assert "conversation_id" in data
    assert data["conversation_id"]  # non-empty string


@pytest.mark.asyncio
async def test_agent_execute_no_tool_calls(mock_settings):
    """POST /api/agent/execute returns an empty actions list when no tools were called."""
    with patch("app.routers.agent.create_default_registry") as mock_registry_factory, \
         patch("app.routers.agent.create_agent_brain") as mock_create_brain, \
         patch("app.routers.agent.run_agent", AsyncMock(return_value={
             "response": "Hello! How can I help?",
             "actions": [],
             "messages": [],
         })):

        mock_registry = MagicMock()
        mock_registry.to_langchain_tools.return_value = []
        mock_registry_factory.return_value = mock_registry
        mock_create_brain.return_value = MagicMock()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/agent/execute",
                json={
                    "message": "Hello",
                    "provider": "openai",
                    "model": "gpt-4o",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "Hello! How can I help?"
    assert data["actions"] == []
    assert "conversation_id" in data


@pytest.mark.asyncio
async def test_agent_execute_preserves_supplied_conversation_id(mock_settings):
    """POST /api/agent/execute preserves a caller-supplied conversation_id."""
    supplied_id = "my-convo-abc-123"

    with patch("app.routers.agent.create_default_registry") as mock_registry_factory, \
         patch("app.routers.agent.create_agent_brain") as mock_create_brain, \
         patch("app.routers.agent.run_agent", AsyncMock(return_value={
             "response": "Got it",
             "actions": [],
             "messages": [],
         })):

        mock_registry = MagicMock()
        mock_registry.to_langchain_tools.return_value = []
        mock_registry_factory.return_value = mock_registry
        mock_create_brain.return_value = MagicMock()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/agent/execute",
                json={
                    "message": "Continue",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "conversation_id": supplied_id,
                },
            )

    assert resp.status_code == 200
    assert resp.json()["conversation_id"] == supplied_id


# ---------------------------------------------------------------------------
# Validation errors (422)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_execute_invalid_empty_message():
    """POST /api/agent/execute with an empty message string returns 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/agent/execute",
            json={
                "message": "",
                "provider": "openai",
                "model": "gpt-4o",
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_agent_execute_missing_message_field():
    """POST /api/agent/execute with no message field returns 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/agent/execute",
            json={
                "provider": "openai",
                "model": "gpt-4o",
            },
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Error propagation (500)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_execute_brain_creation_failure_returns_500(mock_settings):
    """POST /api/agent/execute returns 500 when create_agent_brain raises."""
    with patch("app.routers.agent.create_default_registry") as mock_registry_factory, \
         patch("app.routers.agent.create_agent_brain", side_effect=RuntimeError("LLM unavailable")):

        mock_registry = MagicMock()
        mock_registry.to_langchain_tools.return_value = []
        mock_registry_factory.return_value = mock_registry

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/agent/execute",
                json={
                    "message": "Hello",
                    "provider": "openai",
                    "model": "gpt-4o",
                },
            )

    assert resp.status_code == 500
    assert "LLM unavailable" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_agent_execute_run_failure_returns_500(mock_settings):
    """POST /api/agent/execute returns 500 when run_agent raises."""
    with patch("app.routers.agent.create_default_registry") as mock_registry_factory, \
         patch("app.routers.agent.create_agent_brain") as mock_create_brain, \
         patch("app.routers.agent.run_agent", AsyncMock(side_effect=RuntimeError("agent crashed"))):

        mock_registry = MagicMock()
        mock_registry.to_langchain_tools.return_value = []
        mock_registry_factory.return_value = mock_registry
        mock_create_brain.return_value = MagicMock()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/agent/execute",
                json={
                    "message": "Crash please",
                    "provider": "openai",
                    "model": "gpt-4o",
                },
            )

    assert resp.status_code == 500
    assert "agent crashed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Default provider / model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_execute_uses_default_provider_and_model(mock_settings):
    """POST /api/agent/execute without provider/model uses request defaults (openai/gpt-4o)."""
    with patch("app.routers.agent.create_default_registry") as mock_registry_factory, \
         patch("app.routers.agent.create_agent_brain") as mock_create_brain, \
         patch("app.routers.agent.run_agent", AsyncMock(return_value={
             "response": "ok",
             "actions": [],
             "messages": [],
         })):

        mock_registry = MagicMock()
        mock_registry.to_langchain_tools.return_value = []
        mock_registry_factory.return_value = mock_registry
        mock_create_brain.return_value = MagicMock()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/agent/execute",
                json={"message": "Hello"},
            )

    assert resp.status_code == 200
    # Verify create_agent_brain was called with the schema defaults
    call_kwargs = mock_create_brain.call_args
    assert call_kwargs.kwargs["provider"] == "openai"
    assert call_kwargs.kwargs["model"] == "gpt-4o"
