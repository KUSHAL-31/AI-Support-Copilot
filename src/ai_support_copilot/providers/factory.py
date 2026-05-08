from ai_support_copilot.core.config import Settings
from ai_support_copilot.providers.embeddings.base import HashEmbeddingProvider
from ai_support_copilot.providers.embeddings.http_providers import OllamaEmbeddingProvider
from ai_support_copilot.providers.llm.base import FakeLLMProvider
from ai_support_copilot.providers.llm.http_providers import (
    OllamaLLMProvider,
    OpenAICompatibleLLMProvider,
)
from ai_support_copilot.providers.protocols import (
    EmbeddingProvider,
    LLMProvider,
    Reranker,
    VectorStore,
)
from ai_support_copilot.providers.rerankers.simple import LexicalReranker
from ai_support_copilot.providers.vectorstores.memory import InMemoryVectorStore
from ai_support_copilot.providers.vectorstores.qdrant import QdrantVectorStore


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaLLMProvider(settings)
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return OpenAICompatibleLLMProvider(
            "openai",
            "https://api.openai.com/v1",
            settings.openai_api_key.get_secret_value(),
            settings.openai_chat_model,
        )
    if settings.llm_provider == "anthropic" and settings.anthropic_openai_api_key:
        return OpenAICompatibleLLMProvider(
            "anthropic",
            settings.anthropic_openai_base_url,
            settings.anthropic_openai_api_key.get_secret_value(),
            settings.anthropic_chat_model,
        )
    if settings.llm_provider == "openrouter" and settings.openrouter_api_key:
        return OpenAICompatibleLLMProvider(
            "openrouter",
            "https://openrouter.ai/api/v1",
            settings.openrouter_api_key.get_secret_value(),
            settings.openrouter_chat_model,
        )
    if settings.llm_provider == "groq" and settings.groq_api_key:
        return OpenAICompatibleLLMProvider(
            "groq",
            "https://api.groq.com/openai/v1",
            settings.groq_api_key.get_secret_value(),
            settings.groq_chat_model,
        )
    return FakeLLMProvider()


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(settings)
    return HashEmbeddingProvider()


def build_vector_store(settings: Settings) -> VectorStore:
    if settings.vector_store_provider == "qdrant":
        return QdrantVectorStore(settings.qdrant_url)
    return InMemoryVectorStore()


def build_reranker() -> Reranker:
    return LexicalReranker()
