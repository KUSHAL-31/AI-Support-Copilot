from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol

from ai_support_copilot.domain.models import EmbeddedChunk, RetrievalHit


class LLMProvider(Protocol):
    name: str

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str: ...

    async def stream(self, prompt: str, *, temperature: float = 0.0) -> AsyncIterator[str]: ...


class EmbeddingProvider(Protocol):
    name: str
    dimensions: int

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...


class VectorStore(Protocol):
    name: str

    async def upsert_chunks(self, chunks: Sequence[EmbeddedChunk]) -> None: ...

    async def search(
        self,
        tenant_id: str,
        embedding: Sequence[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]: ...

    async def delete_document(self, tenant_id: str, document_id: str) -> None: ...


class Reranker(Protocol):
    name: str

    async def rerank(
        self, query: str, hits: Sequence[RetrievalHit], *, top_k: int
    ) -> list[RetrievalHit]: ...
