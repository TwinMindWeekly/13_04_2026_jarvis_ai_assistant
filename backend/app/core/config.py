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

    # Default provider and model (used for agent chat + tool calling)
    default_provider: str = "openai"
    default_model: str = "gpt-4o"

    # Wikilink generation provider (separate from chat — Ollama local recommended)
    wikilink_provider: str = "ollama"
    wikilink_model: str = "huihui_ai/llama3.2-abliterate:3b"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # CORS
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://localhost:3000"])

    # RAG
    chroma_persist_dir: str = "./chroma_data"
    upload_dir: str = "./uploads"
    default_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
