"""Anthropic Claude LLM provider implementation using the official AsyncAnthropic SDK."""

import logging
from typing import AsyncIterator

import anthropic
from anthropic import AsyncAnthropic, APIConnectionError, AuthenticationError, APIStatusError

from app.core.exceptions import ChatError, ProviderConnectionError
from app.models.schemas import ChatMessage, ChatResponse, MessageRole, StreamChunk, TokenUsage
from app.services.llm_base import BaseLLMProvider

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseLLMProvider):
    """Wraps AsyncAnthropic for chat completions and streaming.

    Claude separates the system prompt from the conversation messages.
    System messages are extracted from the list and passed as the `system` parameter.
    """

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(api_key=api_key, model=model)
        self._client = AsyncAnthropic(api_key=api_key)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _split_messages(
        self, messages: list[ChatMessage]
    ) -> tuple[str, list[dict]]:
        """Return (system_text, non_system_messages) without mutating input."""
        system_parts: list[str] = []
        conversation: list[dict] = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_parts.append(msg.content)
            else:
                conversation.append({"role": msg.role.value, "content": msg.content})
        return "\n\n".join(system_parts), conversation

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """Return a complete chat response from Claude."""
        system_text, conversation = self._split_messages(messages)
        kwargs: dict = dict(
            model=self.model,
            messages=conversation,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if system_text:
            kwargs["system"] = system_text

        try:
            response = await self._client.messages.create(**kwargs)
        except AuthenticationError as exc:
            logger.error("Claude authentication failed: %s", exc)
            raise ChatError(f"Claude authentication error: {exc}") from exc
        except APIConnectionError as exc:
            logger.error("Claude connection error: %s", exc)
            raise ProviderConnectionError("claude", str(exc)) from exc
        except APIStatusError as exc:
            logger.error("Claude API error %s: %s", exc.status_code, exc.message)
            raise ChatError(f"Claude API error {exc.status_code}: {exc.message}") from exc

        content = response.content[0].text if response.content else ""
        usage = TokenUsage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )

        logger.debug(
            "Claude chat complete — model=%s input=%d output=%d",
            self.model,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return ChatResponse(
            content=content,
            provider="claude",
            model=self.model,
            usage=usage,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Yield StreamChunk objects as tokens arrive from Claude."""
        return self._iter_stream(messages, temperature, max_tokens)

    async def _iter_stream(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[StreamChunk]:  # type: ignore[return]
        """Internal async generator that consumes the Anthropic SSE stream."""
        system_text, conversation = self._split_messages(messages)
        kwargs: dict = dict(
            model=self.model,
            messages=conversation,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if system_text:
            kwargs["system"] = system_text

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield StreamChunk(content=text, done=False)
            yield StreamChunk(content="", done=True)
        except AuthenticationError as exc:
            logger.error("Claude authentication failed (stream): %s", exc)
            raise ChatError(f"Claude authentication error: {exc}") from exc
        except APIConnectionError as exc:
            logger.error("Claude connection error (stream): %s", exc)
            raise ProviderConnectionError("claude", str(exc)) from exc
        except APIStatusError as exc:
            logger.error("Claude API error %s (stream): %s", exc.status_code, exc.message)
            raise ChatError(f"Claude API error {exc.status_code}: {exc.message}") from exc

    async def test_connection(self) -> bool:
        """Return True if Claude is reachable and the API key is valid."""
        try:
            await self._client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            logger.debug("Claude connection test passed.")
            return True
        except AuthenticationError:
            logger.warning("Claude connection test failed: invalid API key.")
            return False
        except APIConnectionError:
            logger.warning("Claude connection test failed: cannot reach API.")
            return False
        except anthropic.BadRequestError:
            # Model rejected the minimal prompt but the key is valid
            logger.debug("Claude connection test passed (BadRequestError is acceptable).")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude connection test failed: %s", exc)
            return False
