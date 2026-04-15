"""Abstract base class for all LLM providers."""

import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.models.schemas import ChatMessage, ChatResponse, StreamChunk

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Base interface that every LLM provider must implement.

    All I/O methods are async. Input objects are never mutated.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """Send a list of messages and return a complete response."""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Send a list of messages and yield response chunks as they arrive."""
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify that the provider is reachable and the credentials are valid."""
        ...

    def _format_messages(self, messages: list[ChatMessage]) -> list[dict]:
        """Convert Pydantic ChatMessage objects to plain dicts expected by SDKs."""
        return [{"role": m.role.value, "content": m.content} for m in messages]
