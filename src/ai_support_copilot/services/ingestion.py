from uuid import UUID

from ai_support_copilot.domain.models import (
    Document,
    EmbeddedChunk,
    IngestionJob,
    IngestionJobResponse,
    IngestionJobStatus,
    IngestionJobType,
    IngestionStatus,
    UploadResponse,
)
from ai_support_copilot.providers.protocols import EmbeddingProvider, VectorStore
from ai_support_copilot.repositories.protocols import (
    DocumentRepositoryProtocol,
    IngestionJobRepositoryProtocol,
)
from ai_support_copilot.services.chunking import ChunkingEngine
from ai_support_copilot.services.parsers import DocumentParser, ParsedDocument
from ai_support_copilot.services.text import content_hash


class IngestionService:
    def __init__(
        self,
        *,
        documents: DocumentRepositoryProtocol,
        jobs: IngestionJobRepositoryProtocol,
        parser: DocumentParser,
        chunker: ChunkingEngine,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self._documents = documents
        self._jobs = jobs
        self._parser = parser
        self._chunker = chunker
        self._embeddings = embeddings
        self._vector_store = vector_store

    async def enqueue_file(
        self, *, tenant_id: str, filename: str, payload: bytes
    ) -> IngestionJobResponse:
        job = IngestionJob(
            tenant_id=tenant_id,
            job_type=IngestionJobType.file,
            source_uri=filename,
            title=filename,
            payload={"filename": filename},
            content=payload,
        )
        await self._jobs.enqueue(job)
        return _job_response(job)

    async def enqueue_url(
        self, *, tenant_id: str, url: str, title: str | None = None
    ) -> IngestionJobResponse:
        job = IngestionJob(
            tenant_id=tenant_id,
            job_type=IngestionJobType.url,
            source_uri=url,
            title=title,
            payload={"url": url, "title": title},
        )
        await self._jobs.enqueue(job)
        return _job_response(job)

    async def get_job(self, *, tenant_id: str, job_id: UUID) -> IngestionJob | None:
        return await self._jobs.get(tenant_id, job_id)

    async def process_next_job(self) -> IngestionJob | None:
        job = await self._jobs.claim_next()
        if not job:
            return None
        try:
            if job.job_type == IngestionJobType.file:
                if job.content is None:
                    raise ValueError("file ingestion job is missing content")
                result = await self.ingest_file(
                    tenant_id=job.tenant_id,
                    filename=str(job.payload.get("filename") or job.source_uri),
                    payload=job.content,
                )
            elif job.job_type == IngestionJobType.url:
                result = await self.ingest_url(
                    tenant_id=job.tenant_id,
                    url=str(job.payload.get("url") or job.source_uri),
                    title=job.title,
                )
            else:
                raise ValueError(f"unsupported ingestion job type: {job.job_type}")
            await self._jobs.complete(job.id, result.document_id, result.chunks_indexed)
        except Exception as exc:
            next_status = (
                IngestionJobStatus.failed
                if job.attempts >= job.max_attempts
                else IngestionJobStatus.pending
            )
            await self._jobs.fail(job.id, str(exc), next_status)
            if next_status == IngestionJobStatus.failed:
                raise
        return job

    async def ingest_file(self, *, tenant_id: str, filename: str, payload: bytes) -> UploadResponse:
        parsed = await self._parser.parse_bytes(filename, payload)
        return await self._ingest_parsed(tenant_id=tenant_id, parsed=parsed, source_uri=filename)

    async def ingest_url(
        self, *, tenant_id: str, url: str, title: str | None = None
    ) -> UploadResponse:
        parsed = await self._parser.parse_url(url, title)
        return await self._ingest_parsed(tenant_id=tenant_id, parsed=parsed, source_uri=url)

    async def delete_document(self, tenant_id: str, document_id: UUID) -> None:
        await self._documents.delete_document(tenant_id, document_id)
        await self._vector_store.delete_document(tenant_id, str(document_id))

    async def _ingest_parsed(
        self, *, tenant_id: str, parsed: ParsedDocument, source_uri: str
    ) -> UploadResponse:
        digest = content_hash(parsed.text)
        existing = await self._documents.find_by_hash(tenant_id, digest)
        if existing:
            return UploadResponse(document_id=existing.id, status=existing.status, chunks_indexed=0)
        document = Document(
            tenant_id=tenant_id,
            title=parsed.title,
            source_type=parsed.source_type,
            source_uri=source_uri,
            content_hash=digest,
            metadata=parsed.metadata,
            status=IngestionStatus.processing,
        )
        await self._documents.save_document(document)
        chunks = self._chunker.recursive_chunks(
            tenant_id=tenant_id,
            document_id=document.id,
            text=parsed.text,
            metadata={"title": parsed.title, "source_uri": source_uri} | parsed.metadata,
        )
        vectors = await self._embeddings.embed_texts([chunk.text for chunk in chunks])
        embedded = [
            EmbeddedChunk(**chunk.model_dump(), embedding=vector)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await self._documents.save_chunks(chunks)
        await self._vector_store.upsert_chunks(embedded)
        await self._documents.update_status(document.id, IngestionStatus.completed)
        return UploadResponse(
            document_id=document.id, status=IngestionStatus.completed, chunks_indexed=len(chunks)
        )


def _job_response(job: IngestionJob) -> IngestionJobResponse:
    return IngestionJobResponse(
        job_id=job.id,
        status=job.status,
        document_id=job.document_id,
        chunks_indexed=job.chunks_indexed,
        attempts=job.attempts,
        error=job.error,
    )
