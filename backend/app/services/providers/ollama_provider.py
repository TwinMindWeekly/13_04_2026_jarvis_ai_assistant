"""Ollama LLM provider implementation using the official ollama async SDK."""

import logging
from typing import AsyncIterator

from ollama import AsyncClient, ResponseError

from app.core.exceptions import ChatError, ProviderConnectionError
from app.models.schemas import ChatMessage, ChatResponse, StreamChunk, TokenUsage
from app.services.llm_base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Wraps the Ollama AsyncClient for local model inference.

    Ollama does not require an API key — the constructor accepts a base_url
    that points to the running Ollama server (default: http://localhost:11434).
    """

    def __init__(self, base_url: str, model: str) -> None:
        # Pass empty string as api_key to satisfy the base class signature.
        super().__init__(api_key="", model=model)
        self._base_url = base_url
        self._client = AsyncClient(host=base_url)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """Return a complete chat response from the local Ollama instance."""
        formatted = self._format_messages(messages)
        try:
            response = await self._client.chat(
                model=self.model,
                messages=formatted,
                options={"temperature": temperature, "num_predict": max_tokens},
            )
        except ConnectionError as exc:
            logger.error("Ollama connection error: %s", exc)
            raise ProviderConnectionError(
                "ollama", f"Cannot reach Ollama at {self._base_url}. Is it running?"
            ) from exc
        except ResponseError as exc:
            logger.error("Ollama API error: %s", exc)
            raise ChatError(f"Ollama error: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            logger.error("Ollama unexpected error: %s", exc)
            raise ChatError(f"Ollama unexpected error: {exc}") from exc

        content = response.message.content or ""
        usage: TokenUsage | None = None
        if hasattr(response, "prompt_eval_count") and response.prompt_eval_count is not None:
            prompt_tokens = response.prompt_eval_count
            completion_tokens = getattr(response, "eval_count", 0) or 0
            usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )

        logger.debug("Ollama chat complete — model=%s", self.model)
        return ChatResponse(
            content=content,
            provider="ollama",
            model=self.model,
            usage=usage,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Yield StreamChunk objects as tokens arrive from Ollama."""
        return self._iter_stream(messages, temperature, max_tokens)

    async def _iter_stream(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[StreamChunk]:  # type: ignore[return]
        """Internal async generator that consumes the Ollama streaming response."""
        formatted = self._format_messages(messages)
        try:
            async for chunk in await self._client.chat(
                model=self.model,
                messages=formatted,
                options={"temperature": temperature, "num_predict": max_tokens},
                stream=True,
            ):
                delta = chunk.message.content or ""
                if delta:
                    yield StreamChunk(content=delta, done=False)
            yield StreamChunk(content="", done=True)
        except ConnectionError as exc:
            logger.error("Ollama stream connection error: %s", exc)
            raise ProviderConnectionError(
                "ollama", f"Cannot reach Ollama at {self._base_url}. Is it running?"
            ) from exc
        except ResponseError as exc:
            logger.error("Ollama stream API error: %s", exc)
            raise ChatError(f"Ollama stream error: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            logger.error("Ollama stream unexpected error: %s", exc)
            raise ChatError(f"Ollama stream unexpected error: {exc}") from exc

    async def test_connection(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            await self._client.list()
            logger.debug("Ollama connection test passed — base_url=%s", self._base_url)
            return True
        except ConnectionError:
            logger.warning(
                "Ollama connection test failed: server not running at %s.", self._base_url
            )
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ollama connection test failed: %s", exc)
            return False
