"""LLM provider factory — maps provider names to their concrete implementations."""

import logging

from app.core.exceptions import ProviderAuthError, ProviderNotFoundError
from app.services.llm_base import BaseLLMProvider

logger = logging.getLogger(__name__)

# Lazy imports inside create() keep startup fast and avoid import errors when a
# provider's SDK is not installed (only the chosen provider is loaded at runtime).
_CLOUD_PROVIDERS = {"openai", "gemini", "claude"}


class LLMFactory:
    """Static factory that constructs the correct BaseLLMProvider subclass."""

    @staticmethod
    def create(
        provider: str,
        model: str,
        api_key: str = "",
        base_url: str = "",
    ) -> BaseLLMProvider:
        """Instantiate and return the provider matching *provider*.

        Args:
            provider: One of "openai", "gemini", "claude", "ollama".
            model:    Model identifier passed directly to the provider SDK.
            api_key:  Required for cloud providers; ignored for Ollama.
            base_url: Used by Ollama to locate the local server; ignored for
                      cloud providers.

        Raises:
            ProviderNotFoundError: When *provider* is not supported.
            ProviderAuthError:     When a cloud provider is requested but
                                   *api_key* is empty.
        """
        provider = provider.strip().lower()

        if provider not in {*_CLOUD_PROVIDERS, "ollama"}:
            logger.error("Unknown provider requested: %s", provider)
            raise ProviderNotFoundError(provider)

        if provider in _CLOUD_PROVIDERS and not api_key:
            logger.error("Missing API key for cloud provider: %s", provider)
            raise ProviderAuthError(provider)

        if provider == "openai":
            from app.services.providers.openai_provider import OpenAIProvider
            logger.debug("Creating OpenAIProvider — model=%s", model)
            return OpenAIProvider(api_key=api_key, model=model)

        if provider == "gemini":
            from app.services.providers.gemini_provider import GeminiProvider
            logger.debug("Creating GeminiProvider — model=%s", model)
            return GeminiProvider(api_key=api_key, model=model)

        if provider == "claude":
            from app.services.providers.claude_provider import ClaudeProvider
            logger.debug("Creating ClaudeProvider — model=%s", model)
            return ClaudeProvider(api_key=api_key, model=model)

        # provider == "ollama"
        from app.services.providers.ollama_provider import OllamaProvider
        logger.debug("Creating OllamaProvider — model=%s base_url=%s", model, base_url)
        return OllamaProvider(base_url=base_url, model=model)
