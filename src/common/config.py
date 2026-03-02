"""Pydantic Settings — all configuration from environment variables.

Copy .env.example to .env and edit. Never hardcode values here.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database (pgvector) ──────────────────────────────────────────────────
    db_password: str = "changeme"
    db_host: str = "localhost"
    db_port: int = 5434
    db_name: str = "fund_copilot"
    db_user: str = "copilot"

    @property
    def db_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def async_db_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ── Ollama ───────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # ── Embeddings ───────────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    embedding_batch_size: int = 64

    # ── Retrieval ────────────────────────────────────────────────────────────
    default_top_k: int = 10
    hybrid_vector_weight: float = 0.6
    hybrid_keyword_weight: float = 0.4
    max_context_chunks: int = 12

    # ── Chunking ─────────────────────────────────────────────────────────────
    chunk_size_tokens: int = 700
    chunk_overlap_tokens: int = 100

    # ── API ──────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8010

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "json"  # "json" | "console"


settings = Settings()
