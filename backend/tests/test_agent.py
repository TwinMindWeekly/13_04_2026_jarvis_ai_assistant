"""Tests for the agent brain: create_agent_brain, run_agent, stream_agent."""

import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.brain import create_agent_brain, run_agent, stream_agent
from app.core.exceptions import ProviderAuthError, ProviderNotFoundError


# ---------------------------------------------------------------------------
# Helpers — inject fake LangChain provider modules (same pattern as test_llm_factory)
# ---------------------------------------------------------------------------

def _inject_fake_lc_module(module_path: str, class_name: str) -> MagicMock:
    """Inject a stub into sys.modules so lazy imports inside brain.py succeed."""
    fake_cls = MagicMock(name=class_name)
    fake_module = types.ModuleType(module_path)
    setattr(fake_module, class_name, fake_cls)
    sys.modules[module_path] = fake_module
    return fake_cls


def _remove_fake_module(module_path: str) -> None:
    sys.modules.pop(module_path, None)


# ---------------------------------------------------------------------------
# create_agent_brain
# ---------------------------------------------------------------------------


def test_create_agent_brain_openai():
    """create_agent_brain() with 'openai' returns a CompiledStateGraph."""
    from langgraph.graph.state import CompiledStateGraph

    lc_mod = "langchain_openai"
    _remove_fake_module(lc_mod)
    fake_chat_cls = _inject_fake_lc_module(lc_mod, "ChatOpenAI")
    fake_llm = MagicMock()
    fake_chat_cls.return_value = fake_llm

    try:
        with patch("app.agent.brain.settings") as mock_settings, \
             patch("app.agent.brain.create_react_agent") as mock_create_react:
            mock_settings.openai_api_key = "test-key-openai"
            fake_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_react.return_value = fake_graph

            mock_settings.openai_base_url = ""
            mock_settings.openai_model = "gpt-4o"
            brain, actual_prov, actual_model = create_agent_brain(
                provider="openai",
                model="gpt-4o",
                tools=[],
            )
    finally:
        _remove_fake_module(lc_mod)

    assert brain is fake_graph
    mock_create_react.assert_called_once()


def test_create_agent_brain_unknown_raises():
    """create_agent_brain() raises ProviderNotFoundError for an unknown provider."""
    with pytest.raises(ProviderNotFoundError):
        create_agent_brain(provider="totally_unknown", model="x", tools=[])


def test_create_agent_brain_missing_key_raises():
    """create_agent_brain() raises ProviderAuthError when the API key is absent."""
    with patch("app.agent.brain.settings") as mock_settings:
        mock_settings.openai_api_key = ""
        with pytest.raises(ProviderAuthError):
            create_agent_brain(provider="openai", model="gpt-4o", tools=[])


def test_create_agent_brain_gemini_missing_key_raises():
    """create_agent_brain() raises ProviderAuthError for gemini when key missing."""
    with patch("app.agent.brain.settings") as mock_settings:
        mock_settings.google_api_key = ""
        with pytest.raises(ProviderAuthError):
            create_agent_brain(provider="gemini", model="gemini-2.0-flash", tools=[])


def test_create_agent_brain_claude_missing_key_raises():
    """create_agent_brain() raises ProviderAuthError for claude when key missing."""
    with patch("app.agent.brain.settings") as mock_settings:
        mock_settings.anthropic_api_key = ""
        with pytest.raises(ProviderAuthError):
            create_agent_brain(provider="claude", model="claude-sonnet-4-20250514", tools=[])


# ---------------------------------------------------------------------------
# run_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_simple():
    """run_agent() extracts the last AIMessage content as the response."""
    mock_brain = MagicMock()
    mock_brain.ainvoke = AsyncMock(return_value={
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
        ]
    })

    result = await run_agent(mock_brain, "Hello")

    assert result["response"] == "Hi there!"
    assert result["actions"] == []
    assert isinstance(result["messages"], list)


@pytest.mark.asyncio
async def test_run_agent_with_tool_calls():
    """run_agent() populates actions list from ToolMessage instances."""
    mock_brain = MagicMock()
    mock_brain.ainvoke = AsyncMock(return_value={
        "messages": [
            HumanMessage(content="Search for Python"),
            AIMessage(content="I'll search for that."),
            ToolMessage(content="Result: Python is great", tool_call_id="call_1", name="web_search"),
            AIMessage(content="Python is a programming language."),
        ]
    })

    result = await run_agent(mock_brain, "Search for Python")

    assert result["response"] == "Python is a programming language."
    assert len(result["actions"]) == 1
    action = result["actions"][0]
    assert action["step"] == 1
    assert action["tool"] == "web_search"
    assert action["output"] == "Result: Python is great"
    assert action["status"] == "completed"


@pytest.mark.asyncio
async def test_run_agent_multiple_tool_calls():
    """run_agent() collects all ToolMessages in order with incrementing step numbers."""
    mock_brain = MagicMock()
    mock_brain.ainvoke = AsyncMock(return_value={
        "messages": [
            HumanMessage(content="Multi step task"),
            ToolMessage(content="search result", tool_call_id="c1", name="web_search"),
            ToolMessage(content="screenshot taken", tool_call_id="c2", name="screenshot"),
            AIMessage(content="Done!"),
        ]
    })

    result = await run_agent(mock_brain, "Multi step task")

    assert result["response"] == "Done!"
    assert len(result["actions"]) == 2
    assert result["actions"][0]["step"] == 1
    assert result["actions"][0]["tool"] == "web_search"
    assert result["actions"][1]["step"] == 2
    assert result["actions"][1]["tool"] == "screenshot"


@pytest.mark.asyncio
async def test_run_agent_no_ai_message_returns_empty_response():
    """run_agent() returns an empty response string when messages list is empty."""
    mock_brain = MagicMock()
    mock_brain.ainvoke = AsyncMock(return_value={"messages": []})

    result = await run_agent(mock_brain, "Hello")

    assert result["response"] == ""
    assert result["actions"] == []


@pytest.mark.asyncio
async def test_run_agent_passes_recursion_limit():
    """run_agent() forwards the recursion_limit to brain.ainvoke via config."""
    mock_brain = MagicMock()
    mock_brain.ainvoke = AsyncMock(return_value={
        "messages": [AIMessage(content="ok")]
    })

    await run_agent(mock_brain, "test", recursion_limit=5)

    call_kwargs = mock_brain.ainvoke.call_args
    config = call_kwargs[1]["config"] if "config" in call_kwargs[1] else call_kwargs[0][1]
    assert config["recursion_limit"] == 5


# ---------------------------------------------------------------------------
# stream_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_agent_yields_events():
    """stream_agent() converts raw LangGraph events to typed dicts and ends with 'done'."""
    async def fake_events(*args, **kwargs):
        yield {"event": "on_tool_start", "name": "web_search", "data": {"input": {"query": "test"}}}
        yield {"event": "on_tool_end", "name": "web_search", "data": {"output": "results here"}}
        yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="Hello")}}

    mock_brain = MagicMock()
    mock_brain.astream_events = fake_events

    events = []
    async for event in stream_agent(mock_brain, "test"):
        events.append(event)

    assert len(events) == 4  # action, action_result, text, done

    assert events[0]["type"] == "action"
    assert events[0]["tool"] == "web_search"
    assert events[0]["input"] == {"query": "test"}
    assert events[0]["status"] == "running"

    assert events[1]["type"] == "action_result"
    assert events[1]["tool"] == "web_search"
    assert events[1]["output"] == "results here"
    assert events[1]["status"] == "completed"

    assert events[2]["type"] == "text"
    assert events[2]["content"] == "Hello"
    assert events[2]["done"] is False

    assert events[3]["type"] == "done"


@pytest.mark.asyncio
async def test_stream_agent_always_ends_with_done():
    """stream_agent() always yields a final 'done' event even if no other events."""
    async def fake_empty_events(*args, **kwargs):
        return
        yield  # make it an async generator

    mock_brain = MagicMock()
    mock_brain.astream_events = fake_empty_events

    events = []
    async for event in stream_agent(mock_brain, "test"):
        events.append(event)

    assert len(events) == 1
    assert events[0]["type"] == "done"


@pytest.mark.asyncio
async def test_stream_agent_skips_empty_text_chunks():
    """stream_agent() does not yield text events for chunks with empty content."""
    async def fake_events(*args, **kwargs):
        yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="")}}
        yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content=None)}}
        yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="real text")}}

    mock_brain = MagicMock()
    mock_brain.astream_events = fake_events

    events = []
    async for event in stream_agent(mock_brain, "test"):
        events.append(event)

    # Only the non-empty chunk + the final done event
    text_events = [e for e in events if e["type"] == "text"]
    assert len(text_events) == 1
    assert text_events[0]["content"] == "real text"


@pytest.mark.asyncio
async def test_stream_agent_ignores_unknown_event_types():
    """stream_agent() silently ignores unrecognised event kinds."""
    async def fake_events(*args, **kwargs):
        yield {"event": "on_something_unknown", "name": "x", "data": {}}
        yield {"event": "on_chain_start", "name": "x", "data": {}}

    mock_brain = MagicMock()
    mock_brain.astream_events = fake_events

    events = []
    async for event in stream_agent(mock_brain, "test"):
        events.append(event)

    # Only the done event
    assert events == [{"type": "done"}]


@pytest.mark.asyncio
async def test_stream_agent_tool_end_none_output():
    """stream_agent() converts None tool output to an empty string."""
    async def fake_events(*args, **kwargs):
        yield {"event": "on_tool_end", "name": "screenshot", "data": {"output": None}}

    mock_brain = MagicMock()
    mock_brain.astream_events = fake_events

    events = []
    async for event in stream_agent(mock_brain, "test"):
        events.append(event)

    result_event = events[0]
    assert result_event["type"] == "action_result"
    assert result_event["output"] == ""
