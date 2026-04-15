"""Agent router — exposes POST /api/agent/execute and WS /ws/agent."""

import json
import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.agent.brain import create_agent_brain, run_agent, stream_agent
from app.core.config import settings
from app.models.agent_schemas import ActionStep, AgentExecuteRequest, AgentExecuteResponse
from app.tools import create_default_registry

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PROVIDER_KEY_MAP: dict[str, str] = {}


def _resolve_api_key(provider: str) -> str:
    """Return the configured API key for *provider* from settings."""
    key_map: dict[str, str] = {
        "openai": settings.openai_api_key,
        "gemini": settings.google_api_key,
        "claude": settings.anthropic_api_key,
        "ollama": "",
    }
    return key_map.get(provider.lower(), "")


# ---------------------------------------------------------------------------
# REST endpoint
# ---------------------------------------------------------------------------

@router.post("/api/agent/execute", response_model=AgentExecuteResponse)
async def execute_agent(request: AgentExecuteRequest) -> AgentExecuteResponse:
    """Execute the ReAct agent with the registered tool set and return the result.

    The agent runs the full LangGraph ReAct loop (Think → Act → Observe) and
    returns the final response together with the tool-call action history so the
    frontend ActionViewer can display each step.
    """
    # Build tool registry and convert to LangChain-compatible tools.
    registry = create_default_registry()
    lc_tools = registry.to_langchain_tools()

    # Create the agent brain for the requested provider / model.
    try:
        brain = create_agent_brain(
            provider=request.provider,
            model=request.model,
            tools=lc_tools,
        )
    except Exception as exc:
        logger.exception(
            "Failed to create agent brain (provider=%s model=%s): %s",
            request.provider,
            request.model,
            exc,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Generate a conversation ID when the client does not supply one.
    conversation_id = request.conversation_id or str(uuid4())

    # Run the agent and collect the structured result.
    try:
        result = await run_agent(brain, request.message)
    except Exception as exc:
        logger.exception("Agent execution failed (conversation_id=%s): %s", conversation_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Map raw action dicts to ActionStep schema objects.
    actions: list[ActionStep] = [
        ActionStep(
            step=action.get("step", idx + 1),
            tool=action.get("tool", "unknown"),
            input=action.get("input") or {},
            output=action.get("output", ""),
            status=action.get("status", "completed"),
            duration_ms=action.get("duration_ms", 0.0),
        )
        for idx, action in enumerate(result.get("actions", []))
    ]

    return AgentExecuteResponse(
        conversation_id=conversation_id,
        response=result.get("response", ""),
        actions=actions,
    )


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket) -> None:
    """Stream agent execution events to the client over a WebSocket connection.

    Expected incoming JSON payload::

        {
            "message":  "<user text>",
            "provider": "openai",          // optional, defaults to settings
            "model":    "gpt-4o"           // optional, defaults to settings
        }

    The server yields one JSON object per event until the agent finishes or
    the connection is closed by the client.
    """
    await websocket.accept()
    logger.debug("WebSocket /ws/agent connection accepted")

    try:
        # Read the initial JSON message from the client.
        raw = await websocket.receive_text()
        try:
            payload: dict = json.loads(raw)
        except json.JSONDecodeError as exc:
            await websocket.send_text(
                json.dumps({"type": "error", "detail": f"Invalid JSON: {exc}"})
            )
            await websocket.close()
            return

        message: str = payload.get("message", "").strip()
        if not message:
            await websocket.send_text(
                json.dumps({"type": "error", "detail": "Field 'message' is required and must not be empty."})
            )
            await websocket.close()
            return

        provider: str = payload.get("provider", settings.default_provider)
        model: str = payload.get("model", settings.default_model)

        # Build the tool registry and the agent brain.
        registry = create_default_registry()
        lc_tools = registry.to_langchain_tools()

        try:
            brain = create_agent_brain(provider=provider, model=model, tools=lc_tools)
        except Exception as exc:
            logger.exception("WebSocket: failed to create agent brain: %s", exc)
            await websocket.send_text(
                json.dumps({"type": "error", "detail": str(exc)})
            )
            await websocket.close()
            return

        # Stream agent events and forward each as a JSON message.
        async for event in stream_agent(brain, message):
            try:
                await websocket.send_text(json.dumps(event))
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected during streaming")
                return

    except WebSocketDisconnect:
        logger.info("WebSocket /ws/agent client disconnected")
    except Exception as exc:
        logger.exception("Unexpected WebSocket error: %s", exc)
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "detail": str(exc)})
            )
        except Exception:
            pass  # Connection may already be closed; nothing to do.
    finally:
        logger.debug("WebSocket /ws/agent connection closed")
