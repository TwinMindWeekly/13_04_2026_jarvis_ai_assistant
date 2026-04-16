"""Pydantic schemas for the agent execution endpoints."""

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in conversation history."""
    role: str  # "user" or "assistant"
    content: str


class AgentExecuteRequest(BaseModel):
    """Request body for POST /api/agent/execute."""

    message: str = Field(..., min_length=1, max_length=10000)
    provider: str = "auto"
    model: str = ""
    language: str = "en"
    conversation_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ActionStep(BaseModel):
    """Represents a single tool-call step taken by the agent."""

    step: int
    tool: str
    input: dict = {}
    output: str = ""
    status: str = "completed"
    duration_ms: float = 0.0


class AgentExecuteResponse(BaseModel):
    """Response body for POST /api/agent/execute."""

    conversation_id: str
    response: str
    actions: list[ActionStep] = []
    provider: str = ""
    model: str = ""
