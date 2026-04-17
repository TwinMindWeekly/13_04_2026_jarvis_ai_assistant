import logging
import time
from datetime import date
from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent
from langgraph.graph.state import CompiledStateGraph

from app.agent.prompts import JARVIS_SYSTEM_PROMPT
from app.core.config import settings
from app.core.exceptions import ProviderNotFoundError, ProviderAuthError
from app.skills.loader import skill_loader

logger = logging.getLogger(__name__)


def _build_llm(provider: str, model: str = ""):
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
        kwargs = {"model": model or settings.openai_model, "api_key": settings.openai_api_key, "temperature": 0}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return ChatOpenAI(**kwargs)

    if provider == "gemini":
        if not settings.google_api_key:
            raise ProviderAuthError("gemini")
        if settings.gemini_base_url:
            # Proxy mode: route through OpenAI-compatible endpoint
            from langchain_openai import ChatOpenAI  # noqa: PLC0415
            return ChatOpenAI(
                model=model or settings.gemini_model,
                base_url=settings.gemini_base_url,
                api_key=settings.google_api_key,
                temperature=0,
            )
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415
        return ChatGoogleGenerativeAI(
            model=model or settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0,
        )

    if provider == "claude":
        if not settings.anthropic_api_key:
            raise ProviderAuthError("claude")
        if settings.anthropic_base_url:
            # Proxy mode: route through OpenAI-compatible endpoint.
            # Antigravity and similar proxies use OpenAI protocol for all
            # providers, so we must use ChatOpenAI (not ChatAnthropic) to
            # get proper tool calling support.
            from langchain_openai import ChatOpenAI  # noqa: PLC0415
            return ChatOpenAI(
                model=model or settings.claude_model,
                base_url=settings.anthropic_base_url + "/v1",
                api_key=settings.anthropic_api_key,
                temperature=0,
            )
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415
        return ChatAnthropic(
            model=model or settings.claude_model,
            api_key=settings.anthropic_api_key,
            temperature=0,
        )

    if provider == "groq":
        if not settings.groq_api_key:
            raise ProviderAuthError("groq")
        from langchain_openai import ChatOpenAI  # noqa: PLC0415
        return ChatOpenAI(
            model=model or settings.groq_model,
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key,
            temperature=0,
        )

    if provider == "sambanova":
        if not settings.sambanova_api_key:
            raise ProviderAuthError("sambanova")
        from langchain_openai import ChatOpenAI  # noqa: PLC0415
        return ChatOpenAI(
            model=model or settings.sambanova_model,
            base_url=settings.sambanova_base_url,
            api_key=settings.sambanova_api_key,
            temperature=0,
        )

    if provider == "ollama":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415
        return ChatOpenAI(
            model=model or "huihui_ai/llama3.2-abliterate:3b",
            base_url=settings.ollama_base_url + "/v1",
            api_key="ollama",
            temperature=0,
        )

    raise ProviderNotFoundError(provider)


# ---------------------------------------------------------------------------
# Auto-fallback provider chain
# ---------------------------------------------------------------------------

# Order: groq (fast+free) → gemini (free tier) → sambanova (free) → openai → claude → ollama
_FALLBACK_CHAIN: list[tuple[str, str]] = []


def _build_fallback_chain() -> list[tuple[str, str]]:
    """Build the ordered list of (provider, model) to try, based on available keys.

    Priority: gemini (fast) → claude → openai → groq → sambanova → ollama.
    """
    chain: list[tuple[str, str]] = []
    if settings.google_api_key:
        chain.append(("gemini", settings.gemini_model))
    if settings.anthropic_api_key:
        chain.append(("claude", settings.claude_model))
    if settings.openai_api_key:
        chain.append(("openai", settings.openai_model))
    if settings.groq_api_key:
        chain.append(("groq", settings.groq_model))
    if settings.sambanova_api_key:
        chain.append(("sambanova", settings.sambanova_model))
    # Ollama as last resort (local, always available if server is running)
    chain.append(("ollama", "huihui_ai/llama3.2-abliterate:3b"))
    return chain


def build_llm_with_fallback(provider: str, model: str):
    """Build LLM, using auto-fallback chain if provider is 'auto'.

    For non-auto providers, delegates directly to _build_llm.
    """
    if provider.lower() != "auto":
        return _build_llm(provider, model), provider, model

    chain = _build_fallback_chain()
    errors: list[str] = []

    for prov, mod in chain:
        try:
            llm = _build_llm(prov, mod)
            logger.info("Auto-fallback: using %s / %s", prov, mod)
            return llm, prov, mod
        except Exception as exc:
            errors.append(f"{prov}: {exc}")
            logger.warning("Auto-fallback: %s failed — %s, trying next...", prov, exc)

    raise ProviderAuthError(
        f"All providers failed: {'; '.join(errors)}"
    )


_LANGUAGE_LABELS = {"vi": "Vietnamese", "en": "English"}


def create_agent_brain(
    provider: str,
    model: str,
    tools: list,
    language: str = "en",
    user_message: str = "",
) -> tuple[CompiledStateGraph, str, str]:
    """Build and return a compiled LangGraph ReAct agent.

    Args:
        provider: One of "openai", "gemini", "claude", "groq", "sambanova",
                  "ollama", or "auto" (fallback chain).
        model: Model name understood by the chosen provider. Empty string
               for auto-detection.
        tools: List of LangChain-compatible tool objects to bind.
        language: User's chosen response language code (e.g. "en", "vi").
        user_message: The user's message, used for skill matching.

    Returns:
        Tuple of (compiled StateGraph, actual_provider, actual_model).
    """
    llm, actual_provider, actual_model = build_llm_with_fallback(provider, model)

    lang_label = _LANGUAGE_LABELS.get(language, language)
    system_prompt = JARVIS_SYSTEM_PROMPT.format(date=date.today().isoformat(), language=lang_label)

    # Auto-inject matched skills into the system prompt
    if user_message:
        skill_section = skill_loader.get_prompt_injection(user_message)
        if skill_section:
            system_prompt += skill_section
            logger.info("Injected skills into prompt for message: %.80s...", user_message)

    brain = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )

    logger.debug("Agent brain created — provider=%s model=%s tools=%d", actual_provider, actual_model, len(tools))
    return brain, actual_provider, actual_model


def _build_history_messages(history: list[dict]) -> list:
    """Convert chat history dicts to LangChain message objects."""
    msgs = []
    for msg in history:
        if msg.get("role") == "user":
            msgs.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            msgs.append(AIMessage(content=msg["content"]))
    return msgs


async def run_agent(
    brain: CompiledStateGraph,
    user_message: str,
    recursion_limit: int = 15,
    history: list[dict] | None = None,
) -> dict:
    """Invoke the agent and return a structured result dict.

    Args:
        brain: Compiled agent graph from create_agent_brain().
        user_message: The user's raw text input.
        recursion_limit: Maximum ReAct loop iterations.
        history: Optional conversation history as list of {"role", "content"} dicts.

    Returns:
        {
            "response": str,          # Final assistant text
            "actions": list[dict],    # Tool call log for ActionViewer
            "messages": list,         # Full message history
        }
    """
    config: dict = {"recursion_limit": recursion_limit}

    input_messages = _build_history_messages(history or [])
    input_messages.append(HumanMessage(content=user_message))

    try:
        result = await brain.ainvoke(
            {"messages": input_messages},
            config=config,
        )
    except Exception as exc:
        logger.exception("Agent invocation failed: %s", exc)
        raise

    messages = result.get("messages", [])

    # Extract the final text response from the last AI message.
    # Gemini 2.5 returns content as list of dicts: [{"type": "text", "text": "..."}, ...]
    final_response: str = ""
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if not content or isinstance(msg, ToolMessage):
            continue
        if isinstance(content, str):
            final_response = content
            break
        if isinstance(content, list):
            # Concatenate all text blocks, skip thinking/signature blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text" and block.get("text"):
                        text_parts.append(block["text"])
                elif isinstance(block, str):
                    text_parts.append(block)
            if text_parts:
                final_response = "\n".join(text_parts)
                break

    # Fallback when recursion limit exhausted without a final AI message.
    if not final_response:
        actions_count = sum(1 for m in messages if isinstance(m, ToolMessage))
        if actions_count:
            final_response = (
                f"I completed {actions_count} action(s) but ran out of processing steps "
                f"before I could summarize the results. The actions above show what was done."
            )
            logger.warning("Recursion limit likely hit — %d tool calls but no final AI response", actions_count)

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
    recursion_limit: int = 15,
    history: list[dict] | None = None,
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
        history: Optional conversation history as list of {"role", "content"} dicts.
    """
    config: dict = {"recursion_limit": recursion_limit}

    input_messages = _build_history_messages(history or [])
    input_messages.append(HumanMessage(content=user_message))

    try:
        async for event in brain.astream_events(
            {"messages": input_messages},
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
                # Extract .content from ToolMessage; fall back to str() for plain values
                if hasattr(raw_output, "content"):
                    output_str = raw_output.content
                elif raw_output is not None:
                    output_str = str(raw_output)
                else:
                    output_str = ""
                yield {
                    "type": "action_result",
                    "tool": event.get("name", "unknown"),
                    "output": output_str,
                    "status": "completed",
                }

            elif kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk is None:
                    continue
                content = getattr(chunk, "content", None)
                if not content:
                    continue
                # Gemini 2.5 returns list of dicts; extract only "text" blocks
                if isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text" and block.get("text"):
                                text_parts.append(block["text"])
                        elif isinstance(block, str):
                            text_parts.append(block)
                    if not text_parts:
                        continue
                    content = "".join(text_parts)
                yield {
                    "type": "text",
                    "content": content,
                    "done": False,
                }

    except Exception as exc:
        logger.exception("Agent streaming failed: %s", exc)
        raise

    yield {"type": "done"}
