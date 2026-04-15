from pydantic import BaseModel, Field
from enum import Enum


class ProviderName(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"
    OLLAMA = "ollama"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: MessageRole
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    provider: ProviderName = ProviderName.OPENAI
    model: str = "gpt-4o"
    stream: bool = False
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)


class ChatResponse(BaseModel):
    content: str
    provider: str
    model: str
    usage: "TokenUsage | None" = None


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class StreamChunk(BaseModel):
    content: str
    done: bool = False


class ProviderInfo(BaseModel):
    name: str
    available: bool
    models: list[str]


class ProviderTestRequest(BaseModel):
    provider: ProviderName
    api_key: str = ""


class ProviderTestResponse(BaseModel):
    provider: str
    success: bool
    message: str
    latency_ms: float = 0.0


class ErrorResponse(BaseModel):
    detail: str
