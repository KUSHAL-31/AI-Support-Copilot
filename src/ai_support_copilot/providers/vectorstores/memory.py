import math
from collections.abc import Sequence
from typing import Any

from ai_support_copilot.domain.models import DocumentChunk, EmbeddedChunk, RetrievalHit


class InMemoryVectorStore:
    name = "memory"

    def __init__(self) -> None:
        self._chunks: list[EmbeddedChunk] = []

    async def upsert_chunks(self, chunks: Sequence[EmbeddedChunk]) -> None:
        incoming_ids = {chunk.id for chunk in chunks}
        self._chunks = [chunk for chunk in self._chunks if chunk.id not in incoming_ids]
        self._chunks.extend(chunks)

    async def search(
        self,
        tenant_id: str,
        embedding: Sequence[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]:
        del filters
        hits: list[RetrievalHit] = []
        for embedded in self._chunks:
            if embedded.tenant_id != tenant_id:
                continue
            chunk = DocumentChunk(**embedded.model_dump(exclude={"embedding"}))
            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    score=_cosine(embedding, embedded.embedding),
                    source="vector",
                )
            )
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]

    async def delete_document(self, tenant_id: str, document_id: str) -> None:
        self._chunks = [
            chunk
            for chunk in self._chunks
            if not (chunk.tenant_id == tenant_id and str(chunk.document_id) == document_id)
        ]


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot / (left_norm * right_norm)
