from collections.abc import Sequence
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from ai_support_copilot.domain.models import DocumentChunk, EmbeddedChunk, RetrievalHit


class QdrantVectorStore:
    name = "qdrant"

    def __init__(self, url: str, collection: str = "support_copilot_chunks") -> None:
        self._client = AsyncQdrantClient(url=url)
        self._collection = collection

    async def ensure_collection(self, dimensions: int) -> None:
        collections = await self._client.get_collections()
        if any(item.name == self._collection for item in collections.collections):
            return
        await self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE),
        )

    async def upsert_chunks(self, chunks: Sequence[EmbeddedChunk]) -> None:
        if not chunks:
            return
        await self.ensure_collection(len(chunks[0].embedding))
        points = [
            PointStruct(
                id=str(chunk.id),
                vector=chunk.embedding,
                payload=chunk.model_dump(mode="json", exclude={"embedding"}),
            )
            for chunk in chunks
        ]
        await self._client.upsert(collection_name=self._collection, points=points)

    async def search(
        self,
        tenant_id: str,
        embedding: Sequence[float],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]:
        conditions = [FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
        for key, value in (filters or {}).items():
            conditions.append(FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value)))
        response = await self._client.query_points(
            collection_name=self._collection,
            query=list(embedding),
            query_filter=Filter(must=conditions),
            limit=top_k,
        )
        return [
            RetrievalHit(
                chunk=DocumentChunk.model_validate(result.payload),
                score=float(result.score),
                source="vector",
            )
            for result in response.points
            if result.payload
        ]

    async def delete_document(self, tenant_id: str, document_id: str) -> None:
        await self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[
                    FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
                    FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                ]
            ),
        )
