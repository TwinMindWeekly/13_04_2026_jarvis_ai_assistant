from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State for the JARVIS agent graph."""

    # Conversation messages — add_messages reducer merges lists on updates
    messages: Annotated[list[BaseMessage], add_messages]

    # Log of tool calls for frontend ActionViewer.
    # Each entry shape:
    # {
    #   "step": int,
    #   "tool": str,
    #   "input": dict,
    #   "output": dict | str,
    #   "status": "running" | "completed" | "failed",
    #   "duration_ms": int,
    # }
    action_history: list[dict]
