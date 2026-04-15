"""Pydantic schemas for the agent execution endpoints."""

from pydantic import BaseModel, Field


class AgentExecuteRequest(BaseModel):
    """Request body for POST /api/agent/execute."""

    message: str = Field(..., min_length=1, max_length=10000)
    provider: str = "openai"
    model: str = "gpt-4o"
    conversation_id: str | None = None


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
