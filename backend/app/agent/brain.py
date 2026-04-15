import logging
import time
from datetime import date
from typing import AsyncIterator

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent
from langgraph.graph.state import CompiledStateGraph

from app.agent.prompts import JARVIS_SYSTEM_PROMPT
from app.core.config import settings
from app.core.exceptions import ProviderNotFoundError, ProviderAuthError

logger = logging.getLogger(__name__)


def _build_llm(provider: str, model: str):
    """Instantiate the correct LangChain chat model for the given provider.

    Raises:
        ProviderNotFoundError: if the provider string is not recognised.
        ProviderAuthError: if a required API key is absent for cloud providers.
    """
    provider = provider.lower()

    if provider == "openai":
        if not settings.openai_api_key:
            raise ProviderAuthError("openai")
        from langchain_openai import ChatOpenAI  # noqa: PLC0415
        return ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            temperature=0,
        )

    if provider == "gemini":
        if not settings.google_api_key:
            raise ProviderAuthError("gemini")
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            temperature=0,
        )

    if provider == "claude":
        if not settings.anthropic_api_key:
            raise ProviderAuthError("claude")
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415
        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=0,
        )

    if provider == "ollama":
        # Ollama exposes an OpenAI-compatible REST endpoint — no real API key needed.
        from langchain_openai import ChatOpenAI  # noqa: PLC0415
        return ChatOpenAI(
            model=model,
            base_url=settings.ollama_base_url + "/v1",
            api_key="ollama",
            temperature=0,
        )

    raise ProviderNotFoundError(provider)


def create_agent_brain(
    provider: str,
    model: str,
    tools: list,
) -> CompiledStateGraph:
    """Build and return a compiled LangGraph ReAct agent.

    Args:
        provider: One of "openai", "gemini", "claude", "ollama".
        model: Model name understood by the chosen provider.
        tools: List of LangChain-compatible tool objects to bind.

    Returns:
        A compiled LangGraph StateGraph ready for ainvoke / astream_events.
    """
    llm = _build_llm(provider, model)

    system_prompt = JARVIS_SYSTEM_PROMPT.format(date=date.today().isoformat())

    brain = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )

    logger.debug("Agent brain created — provider=%s model=%s tools=%d", provider, model, len(tools))
    return brain


async def run_agent(
    brain: CompiledStateGraph,
    user_message: str,
    recursion_limit: int = 10,
) -> dict:
    """Invoke the agent and return a structured result dict.

    Args:
        brain: Compiled agent graph from create_agent_brain().
        user_message: The user's raw text input.
        recursion_limit: Maximum ReAct loop iterations (default 10).

    Returns:
        {
            "response": str,          # Final assistant text
            "actions": list[dict],    # Tool call log for ActionViewer
            "messages": list,         # Full message history
        }
    """
    config: dict = {"recursion_limit": recursion_limit}

    try:
        result = await brain.ainvoke(
            {"messages": [HumanMessage(content=user_message)]},
            config=config,
        )
    except Exception as exc:
        logger.exception("Agent invocation failed: %s", exc)
        raise

    messages = result.get("messages", [])

    # Extract the final text response from the last AI message.
    final_response: str = ""
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if content and not isinstance(msg, ToolMessage):
            final_response = content if isinstance(content, str) else str(content)
            break

    # Build action history from ToolMessages in the conversation.
    actions: list[dict] = []
    step = 1
    for msg in messages:
        if isinstance(msg, ToolMessage):
            actions.append(
                {
                    "step": step,
                    "tool": getattr(msg, "name", "unknown"),
                    "input": {},  # input captured in on_tool_start during streaming
                    "output": msg.content,
                    "status": "completed",
                    "duration_ms": 0,
                }
            )
            step += 1

    return {
        "response": final_response,
        "actions": actions,
        "messages": messages,
    }


async def stream_agent(
    brain: CompiledStateGraph,
    user_message: str,
    recursion_limit: int = 10,
) -> AsyncIterator[dict]:
    """Stream agent events for real-time frontend updates.

    Yields dicts of the following shapes:
        {"type": "action",        "tool": str, "input": dict, "status": "running"}
        {"type": "action_result", "tool": str, "output": str, "status": "completed"}
        {"type": "text",          "content": str, "done": False}
        {"type": "done"}

    Args:
        brain: Compiled agent graph from create_agent_brain().
        user_message: The user's raw text input.
        recursion_limit: Maximum ReAct loop iterations.
    """
    config: dict = {"recursion_limit": recursion_limit}

    try:
        async for event in brain.astream_events(
            {"messages": [HumanMessage(content=user_message)]},
            version="v2",
            config=config,
        ):
            kind: str = event.get("event", "")
            data: dict = event.get("data", {})

            if kind == "on_tool_start":
                yield {
                    "type": "action",
                    "tool": event.get("name", "unknown"),
                    "input": data.get("input"),
                    "status": "running",
                }

            elif kind == "on_tool_end":
                raw_output = data.get("output")
                yield {
                    "type": "action_result",
                    "tool": event.get("name", "unknown"),
                    "output": str(raw_output) if raw_output is not None else "",
                    "status": "completed",
                }

            elif kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk is None:
                    continue
                content = getattr(chunk, "content", None)
                if not content:
                    continue
                yield {
                    "type": "text",
                    "content": content,
                    "done": False,
                }

    except Exception as exc:
        logger.exception("Agent streaming failed: %s", exc)
        raise

    yield {"type": "done"}
