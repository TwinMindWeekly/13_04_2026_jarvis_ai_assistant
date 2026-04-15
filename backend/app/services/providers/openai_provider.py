"""OpenAI LLM provider implementation using the official AsyncOpenAI SDK."""

import logging
from typing import AsyncIterator

from openai import AsyncOpenAI, APIConnectionError, AuthenticationError, APIStatusError

from app.core.exceptions import ChatError, ProviderConnectionError
from app.models.schemas import ChatMessage, ChatResponse, StreamChunk, TokenUsage
from app.services.llm_base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """Wraps AsyncOpenAI for chat completions and streaming."""

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(api_key=api_key, model=model)
        self._client = AsyncOpenAI(api_key=api_key)

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """Return a complete chat response from OpenAI."""
        formatted = self._format_messages(messages)
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=formatted,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AuthenticationError as exc:
            logger.error("OpenAI authentication failed: %s", exc)
            raise ChatError(f"OpenAI authentication error: {exc}") from exc
        except APIConnectionError as exc:
            logger.error("OpenAI connection error: %s", exc)
            raise ProviderConnectionError("openai", str(exc)) from exc
        except APIStatusError as exc:
            logger.error("OpenAI API error %s: %s", exc.status_code, exc.message)
            raise ChatError(f"OpenAI API error {exc.status_code}: {exc.message}") from exc

        content = response.choices[0].message.content or ""
        usage: TokenUsage | None = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        logger.debug("OpenAI chat complete — model=%s tokens=%s", self.model, response.usage)
        return ChatResponse(
            content=content,
            provider="openai",
            model=self.model,
            usage=usage,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Yield StreamChunk objects as tokens arrive from OpenAI."""
        formatted = self._format_messages(messages)
        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=formatted,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
        except AuthenticationError as exc:
            logger.error("OpenAI authentication failed (stream): %s", exc)
            raise ChatError(f"OpenAI authentication error: {exc}") from exc
        except APIConnectionError as exc:
            logger.error("OpenAI connection error (stream): %s", exc)
            raise ProviderConnectionError("openai", str(exc)) from exc
        except APIStatusError as exc:
            logger.error("OpenAI API error %s (stream): %s", exc.status_code, exc.message)
            raise ChatError(f"OpenAI API error {exc.status_code}: {exc.message}") from exc

        return self._iter_stream(stream)

    async def _iter_stream(self, stream) -> AsyncIterator[StreamChunk]:  # type: ignore[return]
        """Internal async generator that consumes the OpenAI SSE stream."""
        try:
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield StreamChunk(content=delta, done=False)
            yield StreamChunk(content="", done=True)
        except APIConnectionError as exc:
            logger.error("OpenAI stream interrupted: %s", exc)
            raise ProviderConnectionError("openai", str(exc)) from exc
        except APIStatusError as exc:
            logger.error("OpenAI stream API error %s: %s", exc.status_code, exc.message)
            raise ChatError(f"OpenAI stream error {exc.status_code}: {exc.message}") from exc

    async def test_connection(self) -> bool:
        """Return True if OpenAI is reachable and the API key is valid."""
        try:
            await self._client.models.list()
            logger.debug("OpenAI connection test passed.")
            return True
        except AuthenticationError:
            logger.warning("OpenAI connection test failed: invalid API key.")
            return False
        except APIConnectionError:
            logger.warning("OpenAI connection test failed: cannot reach API.")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI connection test failed: %s", exc)
            return False
