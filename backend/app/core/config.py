from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # LLM Provider API Keys
    openai_api_key: str = ""
    google_api_key: str = ""
    anthropic_api_key: str = ""

    # Default provider and model
    default_provider: str = "openai"
    default_model: str = "gpt-4o"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # CORS
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://localhost:3000"])

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
