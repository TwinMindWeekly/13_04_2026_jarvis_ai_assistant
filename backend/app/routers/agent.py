"""Agent router — exposes POST /api/agent/execute and WS /ws/agent.

Supports provider='auto' which tries groq → gemini → sambanova → openai
→ claude → ollama, automatically falling back on quota/auth errors.
Runtime retry: if the agent execution itself hits a quota error (429/503),
the router retries with the next provider in the fallback chain.
"""

import json
import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.agent.brain import (
    create_agent_brain,
    run_agent,
    stream_agent,
    _build_fallback_chain,
)
from app.core.config import settings
from app.models.agent_schemas import ActionStep, AgentExecuteRequest, AgentExecuteResponse
from app.tools import create_default_registry
from app.services.usage_tracker import usage_tracker

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_QUOTA_ERROR_MARKERS = [
    "rate_limit", "rate limit", "quota", "429", "503",
    "token pool is empty", "resource_exhausted", "too many requests",
]


def _is_quota_error(exc: Exception) -> bool:
    """Check if an exception looks like a rate-limit / quota error."""
    msg = str(exc).lower()
    return any(marker in msg for marker in _QUOTA_ERROR_MARKERS)


# ---------------------------------------------------------------------------
# REST endpoint
# ---------------------------------------------------------------------------

@router.post("/api/agent/execute", response_model=AgentExecuteResponse)
async def execute_agent(request: AgentExecuteRequest) -> AgentExecuteResponse:
    """Execute the ReAct agent and return the result.

    When provider='auto', the endpoint tries each provider in the fallback
    chain. If the agent execution hits a quota error at runtime (not just
    at LLM build time), it retries with the next provider automatically.
    """
    registry = create_default_registry()
    lc_tools = registry.to_langchain_tools()
    conversation_id = request.conversation_id or str(uuid4())

    # Determine which providers to try.
    if request.provider.lower() == "auto":
        chain = _build_fallback_chain()
    else:
        chain = [(request.provider, request.model)]

    errors: list[str] = []

    for prov, mod in chain:
        try:
            brain, actual_provider, actual_model = create_agent_brain(
                provider=prov, model=mod, tools=lc_tools,
                language=request.language, user_message=request.message,
            )
        except Exception as exc:
            errors.append(f"{prov}: build failed — {exc}")
            logger.warning("Provider %s build failed: %s, trying next...", prov, exc)
            continue

        try:
            result = await run_agent(brain, request.message)

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

            # Track successful usage.
            usage_tracker.record(
                provider=actual_provider,
                model=actual_model,
            )

            return AgentExecuteResponse(
                conversation_id=conversation_id,
                response=result.get("response", ""),
                actions=actions,
                provider=actual_provider,
                model=actual_model,
            )

        except Exception as exc:
            if _is_quota_error(exc) and len(chain) > 1:
                usage_tracker.record_error(prov, mod, str(exc))
                errors.append(f"{prov}/{mod}: quota error — {exc}")
                logger.warning(
                    "Provider %s/%s hit quota limit: %s — trying next provider...",
                    prov, mod, exc,
                )
                continue
            # Non-quota error — don't retry, raise immediately.
            logger.exception("Agent execution failed (provider=%s): %s", prov, exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # All providers exhausted.
    detail = f"All providers failed: {'; '.join(errors)}"
    logger.error(detail)
    raise HTTPException(status_code=503, detail=detail)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket) -> None:
    """Stream agent execution events over WebSocket.

    Supports provider='auto' with runtime fallback on quota errors.
    """
    await websocket.accept()
    logger.debug("WebSocket /ws/agent connection accepted")

    try:
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
        language: str = payload.get("language", "en")

        registry = create_default_registry()
        lc_tools = registry.to_langchain_tools()

        # Determine provider chain for WebSocket too.
        if provider.lower() == "auto":
            chain = _build_fallback_chain()
        else:
            chain = [(provider, model)]

        streamed = False
        for prov, mod in chain:
            try:
                brain, actual_prov, actual_mod = create_agent_brain(
                    provider=prov, model=mod, tools=lc_tools,
                    language=language, user_message=message,
                )
            except Exception as exc:
                logger.warning("WS: %s build failed: %s, trying next...", prov, exc)
                continue

            try:
                async for event in stream_agent(brain, message):
                    try:
                        await websocket.send_text(json.dumps(event))
                    except WebSocketDisconnect:
                        logger.info("WebSocket client disconnected during streaming")
                        return
                streamed = True
                break
            except Exception as exc:
                if _is_quota_error(exc) and len(chain) > 1:
                    logger.warning("WS: %s/%s quota error: %s — trying next...", prov, mod, exc)
                    continue
                raise

        if not streamed:
            await websocket.send_text(
                json.dumps({"type": "error", "detail": "All providers failed. Check API keys or try again later."})
            )

    except WebSocketDisconnect:
        logger.info("WebSocket /ws/agent client disconnected")
    except Exception as exc:
        logger.exception("Unexpected WebSocket error: %s", exc)
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "detail": str(exc)})
            )
        except Exception:
            pass
    finally:
        logger.debug("WebSocket /ws/agent connection closed")
