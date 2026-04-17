from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field

# Load .env with override=True so project .env always wins over system env vars
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path, override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # LLM Provider API Keys
    openai_api_key: str = ""
    openai_base_url: str = ""  # Custom base URL (e.g. Antigravity proxy)
    google_api_key: str = ""
    gemini_base_url: str = ""  # Custom base URL (e.g. Antigravity proxy)
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""  # Custom base URL (e.g. Antigravity proxy)
    groq_api_key: str = ""
    sambanova_api_key: str = ""

    # Default provider and model (used for agent chat + tool calling)
    # Set to "auto" to enable fallback chain: groq → gemini → sambanova → openai
    default_provider: str = "auto"
    default_model: str = ""

    # Per-provider default models
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-3-flash"
    claude_model: str = "claude-sonnet-4-6"

    # Groq (free tier: 1000 req/day, Llama 3.3 70B with tool calling)
    groq_model: str = "llama-3.3-70b-versatile"

    # SambaNova (free tier: Meta-Llama-3.3-70B-Instruct)
    sambanova_base_url: str = "https://api.sambanova.ai/v1"
    sambanova_model: str = "Meta-Llama-3.3-70B-Instruct"

    # Wikilink generation provider (separate from chat — Ollama local recommended)
    wikilink_provider: str = "ollama"
    wikilink_model: str = "huihui_ai/llama3.2-abliterate:3b"

    # Image generation (separate from chat proxy — DALL-E needs real OpenAI key)
    image_api_key: str = ""  # Defaults to OPENAI_API_KEY if empty
    image_api_base_url: str = "https://api.openai.com/v1"  # Always direct OpenAI unless overridden
    stability_api_key: str = ""

    # Code runner
    godot_path: str = ""  # Path to Godot executable for GDScript execution

    # Email (IMAP/SMTP)
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from_name: str = "JARVIS"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # CORS
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://localhost:3000"])

    # RAG
    chroma_persist_dir: str = "./chroma_data"
    upload_dir: str = "./uploads"
    default_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # SQLite persistence (Phase 1 — documents, wikilinks, Phase 2/3 tables)
    sqlite_path: str = "./jarvis.db"
    # Fernet key for encrypting email passwords (Phase 2). Auto-generated at
    # first startup when empty — warn user to back it up.
    jarvis_secret_key: str = ""

    # Email sync (Phase 2)
    email_sync_interval_minutes: int = 5

    # Jobs refresh (Phase 3) — 24h = 1440min
    jobs_refresh_interval_minutes: int = 1440

    # VieNeu-TTS device: "cpu" (default), "cuda", "mps", "gpu"
    # GPU requires CUDA-enabled llama-cpp-python wheel (the default Windows wheel is CPU-only)
    vieneu_device: str = "cpu"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
