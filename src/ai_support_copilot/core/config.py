from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Enterprise AI Support Copilot"
    app_env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "sqlite+aiosqlite:///:memory:"
    auto_run_migrations: bool = True
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    default_llm_provider: Literal["ollama", "openai", "anthropic", "openrouter", "groq", "fake"] = (
        "fake"
    )
    default_embedding_provider: Literal[
        "ollama", "openai", "huggingface", "sentence_transformers", "local"
    ] = "local"
    default_vectorstore: Literal[
        "qdrant", "pgvector", "pinecone", "weaviate", "chroma", "memory"
    ] = "memory"

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1"
    ollama_embed_model: str = "nomic-embed-text"
    openai_api_key: SecretStr | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    anthropic_api_key: SecretStr | None = None
    anthropic_chat_model: str = "claude-3-5-sonnet-latest"
    openrouter_api_key: SecretStr | None = None
    openrouter_chat_model: str = "openai/gpt-4o-mini"
    groq_api_key: SecretStr | None = None
    groq_chat_model: str = "llama-3.1-70b-versatile"
    pinecone_api_key: SecretStr | None = None
    pinecone_index: str | None = None
    weaviate_url: str | None = None
    weaviate_api_key: SecretStr | None = None
    chroma_host: str = "chroma"
    chroma_port: int = 8000

    rate_limit_per_minute: int = 60
    auth_jwt_secret: SecretStr = SecretStr(
        "dev-only-change-me-to-a-strong-random-secret-before-deploy"
    )
    auth_access_token_minutes: int = 30
    auth_password_min_length: int = 12
    confidence_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    max_context_tokens: int = 3000
    retrieval_top_k: int = 12
    rerank_top_k: int = 6
    chunk_size: int = 900
    chunk_overlap: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
