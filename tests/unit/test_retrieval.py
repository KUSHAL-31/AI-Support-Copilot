from uuid import uuid4

from ai_support_copilot.domain.models import DocumentChunk, EmbeddedChunk
from ai_support_copilot.providers.embeddings.base import HashEmbeddingProvider
from ai_support_copilot.providers.vectorstores.memory import InMemoryVectorStore
from ai_support_copilot.repositories.documents import DocumentRepository
from ai_support_copilot.services.retrieval import HybridRetrievalService


async def test_hybrid_retrieval_is_tenant_scoped() -> None:
    documents = DocumentRepository()
    embeddings = HashEmbeddingProvider()
    vector_store = InMemoryVectorStore()
    chunk = DocumentChunk(
        document_id=uuid4(),
        tenant_id="acme",
        text="Enterprise card payments fail when processor risk checks reject authorization.",
        ordinal=0,
        token_count=12,
        metadata={"title": "Payments"},
    )
    vector = (await embeddings.embed_texts([chunk.text]))[0]
    await documents.save_chunks([chunk])
    await vector_store.upsert_chunks([EmbeddedChunk(**chunk.model_dump(), embedding=vector)])

    retrieval = HybridRetrievalService(
        documents=documents, embeddings=embeddings, vector_store=vector_store
    )
    hits = await retrieval.retrieve(tenant_id="acme", query="card payments failing", top_k=5)
    other_tenant_hits = await retrieval.retrieve(tenant_id="other", query="card payments", top_k=5)

    assert hits
    assert all(hit.chunk.tenant_id == "acme" for hit in hits)
    assert other_tenant_hits == []
