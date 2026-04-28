import asyncio

from ai_support_copilot.core.config import Settings, get_settings
from ai_support_copilot.providers.factory import (
    build_embedding_provider,
    build_llm_provider,
    build_reranker,
    build_vector_store,
)
from ai_support_copilot.repositories.cache import cache
from ai_support_copilot.repositories.db import Database
from ai_support_copilot.repositories.migrations import run_migrations
from ai_support_copilot.repositories.postgres import (
    PostgresConversationRepository,
    PostgresDocumentRepository,
    PostgresIngestionJobRepository,
    PostgresUserRepository,
)
from ai_support_copilot.services.chunking import ChunkingEngine
from ai_support_copilot.services.confidence import ConfidenceScorer
from ai_support_copilot.services.context import ContextBuilder
from ai_support_copilot.services.ingestion import IngestionService
from ai_support_copilot.services.parsers import DocumentParser
from ai_support_copilot.services.retrieval import HybridRetrievalService
from ai_support_copilot.workflows.query_graph import QueryWorkflow


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.postgres_dsn)
        self.documents = PostgresDocumentRepository(self.database.session_factory)
        self.conversations = PostgresConversationRepository(self.database.session_factory)
        self.ingestion_jobs = PostgresIngestionJobRepository(self.database.session_factory)
        self.users = PostgresUserRepository(self.database.session_factory)
        self.cache = cache
        self.embeddings = build_embedding_provider(settings)
        self.vector_store = build_vector_store(settings)
        self.llm = build_llm_provider(settings)
        self.reranker = build_reranker()
        self.chunker = ChunkingEngine(settings.chunk_size, settings.chunk_overlap)
        self.parser = DocumentParser()
        self.ingestion = IngestionService(
            documents=self.documents,
            jobs=self.ingestion_jobs,
            parser=self.parser,
            chunker=self.chunker,
            embeddings=self.embeddings,
            vector_store=self.vector_store,
        )
        self.retrieval = HybridRetrievalService(
            documents=self.documents,
            embeddings=self.embeddings,
            vector_store=self.vector_store,
        )
        self.workflow = QueryWorkflow(
            settings=settings,
            llm=self.llm,
            retrieval=self.retrieval,
            reranker=self.reranker,
            context_builder=ContextBuilder(settings.max_context_tokens),
            confidence=ConfidenceScorer(),
            conversations=self.conversations,
            cache=self.cache,
        )

    async def startup(self) -> None:
        if self.settings.auto_run_migrations:
            await asyncio.to_thread(run_migrations, self.settings.postgres_dsn)

    async def shutdown(self) -> None:
        await self.database.dispose()


_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container(get_settings())
    return _container


def reset_container_for_tests(container: Container | None = None) -> None:
    global _container
    _container = container
