from collections import defaultdict
from uuid import UUID

from ai_support_copilot.domain.models import Document, DocumentChunk, IngestionStatus


class DocumentRepository:
    def __init__(self) -> None:
        self._documents: dict[UUID, Document] = {}
        self._chunks_by_tenant: dict[str, list[DocumentChunk]] = defaultdict(list)
        self._hashes: dict[tuple[str, str], UUID] = {}

    async def find_by_hash(self, tenant_id: str, content_hash: str) -> Document | None:
        document_id = self._hashes.get((tenant_id, content_hash))
        return self._documents.get(document_id) if document_id else None

    async def save_document(self, document: Document) -> Document:
        self._documents[document.id] = document
        self._hashes[(document.tenant_id, document.content_hash)] = document.id
        return document

    async def update_status(
        self, document_id: UUID, status: IngestionStatus, error: str | None = None
    ) -> None:
        document = self._documents[document_id]
        document.status = status
        if error:
            document.metadata["error"] = error

    async def save_chunks(self, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            return
        tenant_id = chunks[0].tenant_id
        existing_ids = {chunk.id for chunk in chunks}
        self._chunks_by_tenant[tenant_id] = [
            chunk for chunk in self._chunks_by_tenant[tenant_id] if chunk.id not in existing_ids
        ]
        self._chunks_by_tenant[tenant_id].extend(chunks)

    async def list_chunks(self, tenant_id: str) -> list[DocumentChunk]:
        return list(self._chunks_by_tenant[tenant_id])

    async def get_document(self, document_id: UUID) -> Document | None:
        return self._documents.get(document_id)

    async def delete_document(self, tenant_id: str, document_id: UUID) -> None:
        self._documents.pop(document_id, None)
        self._chunks_by_tenant[tenant_id] = [
            chunk for chunk in self._chunks_by_tenant[tenant_id] if chunk.document_id != document_id
        ]


document_repository = DocumentRepository()
