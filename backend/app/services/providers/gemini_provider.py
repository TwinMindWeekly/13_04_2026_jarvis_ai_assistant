"""Google Gemini LLM provider implementation using the google-generativeai SDK.

The google-generativeai SDK is synchronous. All blocking calls are wrapped with
asyncio.to_thread() to avoid blocking the FastAPI event loop.
"""

import asyncio
import logging
from typing import AsyncIterator

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPICallError, PermissionDenied, Unauthenticated

from app.core.exceptions import ChatError, ProviderConnectionError
from app.models.schemas import ChatMessage, ChatResponse, MessageRole, StreamChunk, TokenUsage
from app.services.llm_base import BaseLLMProvider

logger = logging.getLogger(__name__)

# Gemini role names differ from the standard "user"/"assistant" convention.
_ROLE_MAP: dict[str, str] = {
    MessageRole.USER.value: "user",
    MessageRole.ASSISTANT.value: "model",
    MessageRole.SYSTEM.value: "user",  # injected as a leading user turn
}


class GeminiProvider(BaseLLMProvider):
    """Wraps google-generativeai (sync) behind asyncio.to_thread for async usage."""

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(api_key=api_key, model=model)
        genai.configure(api_key=api_key)
        self._generative_model = genai.GenerativeModel(model)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_history(self, messages: list[ChatMessage]) -> tuple[list[dict], str | None]:
        """Convert ChatMessage list to Gemini history format.

        System messages have no native slot in the Gemini SDK; they are
        prepended to the first user message as context text.
        Returns (history_without_last, last_user_prompt).
        """
        system_parts: list[str] = [
            m.content for m in messages if m.role == MessageRole.SYSTEM
        ]
        system_prefix = "\n\n".join(system_parts)

        non_system = [m for m in messages if m.role != MessageRole.SYSTEM]

        if not non_system:
            return [], None

        # Convert to Gemini content format
        history: list[dict] = []
        for i, msg in enumerate(non_system[:-1]):
            content = msg.content
            if i == 0 and system_prefix:
                content = f"{system_prefix}\n\n{content}"
            history.append({"role": _ROLE_MAP[msg.role.value], "parts": [content]})

        last = non_system[-1]
        last_content = last.content
        if not non_system[:-1] and system_prefix:
            last_content = f"{system_prefix}\n\n{last_content}"

        return history, last_content

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """Return a complete chat response from Gemini."""
        history, last_prompt = self._build_history(messages)
        if last_prompt is None:
            raise ChatError("No user message found in the conversation.")

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        def _sync_call() -> genai.types.GenerateContentResponse:
            chat_session = self._generative_model.start_chat(history=history)
            return chat_session.send_message(
                last_prompt, generation_config=generation_config
            )

        try:
            response = await asyncio.to_thread(_sync_call)
        except (Unauthenticated, PermissionDenied) as exc:
            logger.error("Gemini authentication error: %s", exc)
            raise ChatError(f"Gemini authentication error: {exc}") from exc
        except GoogleAPICallError as exc:
            logger.error("Gemini API error: %s", exc)
            raise ProviderConnectionError("gemini", str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini unexpected error: %s", exc)
            raise ChatError(f"Gemini error: {exc}") from exc

        content = response.text or ""
        usage: TokenUsage | None = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            usage = TokenUsage(
                prompt_tokens=getattr(meta, "prompt_token_count", 0),
                completion_tokens=getattr(meta, "candidates_token_count", 0),
                total_tokens=getattr(meta, "total_token_count", 0),
            )

        logger.debug("Gemini chat complete — model=%s", self.model)
        return ChatResponse(
            content=content,
            provider="gemini",
            model=self.model,
            usage=usage,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Yield StreamChunk objects as tokens arrive from Gemini."""
        return self._iter_stream(messages, temperature, max_tokens)

    async def _iter_stream(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[StreamChunk]:  # type: ignore[return]
        """Internal async generator that wraps the sync Gemini streaming iterator."""
        history, last_prompt = self._build_history(messages)
        if last_prompt is None:
            raise ChatError("No user message found in the conversation.")

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        def _sync_stream():
            chat_session = self._generative_model.start_chat(history=history)
            return chat_session.send_message(
                last_prompt,
                generation_config=generation_config,
                stream=True,
            )

        try:
            response_stream = await asyncio.to_thread(_sync_stream)
        except (Unauthenticated, PermissionDenied) as exc:
            logger.error("Gemini authentication error (stream): %s", exc)
            raise ChatError(f"Gemini authentication error: {exc}") from exc
        except GoogleAPICallError as exc:
            logger.error("Gemini API error (stream): %s", exc)
            raise ProviderConnectionError("gemini", str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini unexpected error (stream): %s", exc)
            raise ChatError(f"Gemini error: {exc}") from exc

        # The sync iterator must be consumed in a thread to avoid blocking.
        import queue
        import threading

        chunk_queue: queue.Queue = queue.Queue()

        def _consume():
            try:
                for chunk in response_stream:
                    chunk_queue.put(chunk.text)
            except Exception as exc:  # noqa: BLE001
                chunk_queue.put(exc)
            finally:
                chunk_queue.put(None)  # sentinel

        thread = threading.Thread(target=_consume, daemon=True)
        thread.start()

        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, chunk_queue.get)
            if item is None:
                break
            if isinstance(item, Exception):
                raise ChatError(f"Gemini stream error: {item}") from item
            if item:
                yield StreamChunk(content=item, done=False)

        yield StreamChunk(content="", done=True)

    async def test_connection(self) -> bool:
        """Return True if Gemini is reachable and the API key is valid."""
        try:
            await asyncio.to_thread(genai.list_models)
            logger.debug("Gemini connection test passed.")
            return True
        except (Unauthenticated, PermissionDenied):
            logger.warning("Gemini connection test failed: invalid API key.")
            return False
        except GoogleAPICallError:
            logger.warning("Gemini connection test failed: cannot reach API.")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini connection test failed: %s", exc)
            return False
