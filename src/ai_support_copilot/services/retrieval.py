import math
from collections import Counter

from ai_support_copilot.domain.models import DocumentChunk, RetrievalHit
from ai_support_copilot.providers.protocols import EmbeddingProvider, VectorStore
from ai_support_copilot.repositories.documents import DocumentRepository


class HybridRetrievalService:
    def __init__(
        self,
        *,
        documents: DocumentRepository,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
        vector_weight: float = 0.65,
    ) -> None:
        self._documents = documents
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._vector_weight = vector_weight

    async def retrieve(
        self, *, tenant_id: str, query: str, top_k: int, filters: dict | None = None
    ) -> list[RetrievalHit]:
        query_embedding = (await self._embeddings.embed_texts([query]))[0]
        vector_hits = await self._vector_store.search(
            tenant_id, query_embedding, top_k=top_k * 2, filters=filters
        )
        keyword_hits = await self._keyword_search(tenant_id, query, top_k=top_k * 2)
        return self._merge(vector_hits, keyword_hits, top_k=top_k)

    async def _keyword_search(self, tenant_id: str, query: str, top_k: int) -> list[RetrievalHit]:
        chunks = await self._documents.list_chunks(tenant_id)
        query_terms = query.lower().split()
        scored = [
            RetrievalHit(chunk=chunk, score=_bm25_like(query_terms, chunk), source="bm25")
            for chunk in chunks
        ]
        return [
            hit
            for hit in sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]
            if hit.score > 0
        ]

    def _merge(
        self, vector_hits: list[RetrievalHit], keyword_hits: list[RetrievalHit], *, top_k: int
    ) -> list[RetrievalHit]:
        merged: dict[str, RetrievalHit] = {}
        for hit in vector_hits:
            merged[str(hit.chunk.id)] = hit.model_copy(
                update={"score": hit.score * self._vector_weight}
            )
        for hit in keyword_hits:
            key = str(hit.chunk.id)
            keyword_score = hit.score * (1 - self._vector_weight)
            if key in merged:
                merged[key].score += keyword_score
                merged[key].source = "hybrid"
            else:
                merged[key] = hit.model_copy(update={"score": keyword_score})
        return sorted(merged.values(), key=lambda item: item.score, reverse=True)[:top_k]


def _bm25_like(query_terms: list[str], chunk: DocumentChunk) -> float:
    terms = chunk.text.lower().split()
    counts = Counter(terms)
    score = 0.0
    for term in query_terms:
        tf = counts[term]
        if tf:
            score += (tf * 2.2) / (tf + 1.2)
    length_norm = 1 / math.sqrt(max(len(terms), 1))
    return score * length_norm
