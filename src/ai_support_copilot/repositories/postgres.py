from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_support_copilot.domain.models import (
    Citation,
    Conversation,
    ConversationMessage,
    Document,
    DocumentChunk,
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
    IngestionStatus,
    SourceType,
    User,
    UserRole,
)
from ai_support_copilot.repositories.db import (
    ChunkRecord,
    ConversationRecord,
    DocumentRecord,
    IngestionJobRecord,
    MessageRecord,
    TenantRecord,
    UserRecord,
    utcnow,
)


class PostgresUserRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def create(self, user: User) -> User:
        async with self._sessions() as session:
            existing = await session.scalar(
                select(UserRecord).where(UserRecord.email == user.email.lower())
            )
            if existing:
                raise ValueError("email already registered")
            await _ensure_tenant(session, user.tenant_id)
            session.add(
                UserRecord(
                    id=str(user.id),
                    tenant_id=user.tenant_id,
                    email=user.email.lower(),
                    password_hash=user.password_hash,
                    role=user.role.value,
                    is_active=user.is_active,
                    created_at=user.created_at,
                )
            )
            await session.commit()
            user.email = user.email.lower()
            return user

    async def get_by_email(self, email: str) -> User | None:
        async with self._sessions() as session:
            record = await session.scalar(
                select(UserRecord).where(UserRecord.email == email.strip().lower())
            )
            return _user_from_record(record) if record else None

    async def get_by_id(self, user_id: UUID) -> User | None:
        async with self._sessions() as session:
            record = await session.get(UserRecord, str(user_id))
            return _user_from_record(record) if record else None


class PostgresDocumentRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def find_by_hash(self, tenant_id: str, content_hash: str) -> Document | None:
        async with self._sessions() as session:
            record = await session.scalar(
                select(DocumentRecord).where(
                    DocumentRecord.tenant_id == tenant_id,
                    DocumentRecord.content_hash == content_hash,
                )
            )
            return _document_from_record(record) if record else None

    async def save_document(self, document: Document) -> Document:
        async with self._sessions() as session:
            await _ensure_tenant(session, document.tenant_id)
            session.add(_document_to_record(document))
            await session.commit()
            return document

    async def update_status(
        self, document_id: UUID, status: IngestionStatus, error: str | None = None
    ) -> None:
        async with self._sessions() as session:
            record = await session.get(DocumentRecord, str(document_id))
            if not record:
                return
            record.status = status.value
            if error:
                record.metadata_ = dict(record.metadata_ or {}) | {"error": error}
            await session.commit()

    async def save_chunks(self, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            return
        async with self._sessions() as session:
            await _ensure_tenant(session, chunks[0].tenant_id)
            session.add_all([_chunk_to_record(chunk) for chunk in chunks])
            await session.commit()

    async def list_chunks(self, tenant_id: str) -> list[DocumentChunk]:
        async with self._sessions() as session:
            records = (
                await session.scalars(
                    select(ChunkRecord)
                    .where(ChunkRecord.tenant_id == tenant_id)
                    .order_by(ChunkRecord.document_id, ChunkRecord.ordinal)
                )
            ).all()
            return [_chunk_from_record(record) for record in records]

    async def get_document(self, document_id: UUID) -> Document | None:
        async with self._sessions() as session:
            record = await session.get(DocumentRecord, str(document_id))
            return _document_from_record(record) if record else None

    async def delete_document(self, tenant_id: str, document_id: UUID) -> None:
        async with self._sessions() as session:
            await session.execute(
                delete(DocumentRecord).where(
                    DocumentRecord.tenant_id == tenant_id,
                    DocumentRecord.id == str(document_id),
                )
            )
            await session.commit()


class PostgresConversationRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_or_create(self, tenant_id: str, conversation_id: UUID | None) -> Conversation:
        async with self._sessions() as session:
            await _ensure_tenant(session, tenant_id)
            if conversation_id:
                record = await session.get(ConversationRecord, str(conversation_id))
                if record:
                    if record.tenant_id != tenant_id:
                        raise PermissionError("conversation belongs to another tenant")
                    return await self._conversation_with_messages(session, record)
            record = ConversationRecord(id=str(conversation_id or uuid4()), tenant_id=tenant_id)
            session.add(record)
            await session.commit()
            return Conversation(
                id=UUID(record.id),
                tenant_id=tenant_id,
                created_at=record.created_at,
            )

    async def append(self, message: ConversationMessage) -> None:
        async with self._sessions() as session:
            await _ensure_tenant(session, message.tenant_id)
            conversation = await session.get(ConversationRecord, str(message.conversation_id))
            if not conversation:
                session.add(
                    ConversationRecord(id=str(message.conversation_id), tenant_id=message.tenant_id)
                )
            session.add(
                MessageRecord(
                    id=str(message.id),
                    conversation_id=str(message.conversation_id),
                    tenant_id=message.tenant_id,
                    role=message.role,
                    content=message.content,
                    citations=[citation.model_dump(mode="json") for citation in message.citations],
                    created_at=message.created_at,
                )
            )
            await session.commit()

    async def get(self, tenant_id: str, conversation_id: UUID) -> Conversation | None:
        async with self._sessions() as session:
            record = await session.get(ConversationRecord, str(conversation_id))
            if not record or record.tenant_id != tenant_id:
                return None
            return await self._conversation_with_messages(session, record)

    async def _conversation_with_messages(
        self, session: AsyncSession, record: ConversationRecord
    ) -> Conversation:
        messages = (
            await session.scalars(
                select(MessageRecord)
                .where(MessageRecord.conversation_id == record.id)
                .order_by(MessageRecord.created_at)
            )
        ).all()
        return Conversation(
            id=UUID(record.id),
            tenant_id=record.tenant_id,
            created_at=record.created_at,
            messages=[_message_from_record(message) for message in messages],
        )


class PostgresIngestionJobRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def enqueue(self, job: IngestionJob) -> IngestionJob:
        async with self._sessions() as session:
            await _ensure_tenant(session, job.tenant_id)
            session.add(_job_to_record(job))
            await session.commit()
            return job

    async def get(self, tenant_id: str, job_id: UUID) -> IngestionJob | None:
        async with self._sessions() as session:
            record = await session.get(IngestionJobRecord, str(job_id))
            if not record or record.tenant_id != tenant_id:
                return None
            return _job_from_record(record)

    async def claim_next(self) -> IngestionJob | None:
        async with self._sessions() as session, session.begin():
            record = await session.scalar(
                select(IngestionJobRecord)
                .where(IngestionJobRecord.status == IngestionJobStatus.pending.value)
                .order_by(IngestionJobRecord.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not record:
                return None
            record.status = IngestionJobStatus.processing.value
            record.attempts += 1
            record.updated_at = utcnow()
            record.error = None
            return _job_from_record(record)

    async def complete(self, job_id: UUID, document_id: UUID, chunks_indexed: int) -> None:
        async with self._sessions() as session:
            record = await session.get(IngestionJobRecord, str(job_id))
            if not record:
                return
            record.status = IngestionJobStatus.completed.value
            record.document_id = str(document_id)
            record.chunks_indexed = chunks_indexed
            record.updated_at = utcnow()
            record.error = None
            await session.commit()

    async def fail(self, job_id: UUID, error: str, status: IngestionJobStatus) -> None:
        async with self._sessions() as session:
            record = await session.get(IngestionJobRecord, str(job_id))
            if not record:
                return
            record.status = status.value
            record.error = error[:4000]
            record.updated_at = utcnow()
            await session.commit()


async def _ensure_tenant(session: AsyncSession, tenant_id: str) -> None:
    if await session.get(TenantRecord, tenant_id):
        return
    session.add(TenantRecord(id=tenant_id))
    await session.flush()


def _user_from_record(record: UserRecord) -> User:
    return User(
        id=UUID(record.id),
        tenant_id=record.tenant_id,
        email=record.email,
        password_hash=record.password_hash,
        role=UserRole(record.role),
        is_active=record.is_active,
        created_at=record.created_at,
    )


def _document_to_record(document: Document) -> DocumentRecord:
    return DocumentRecord(
        id=str(document.id),
        tenant_id=document.tenant_id,
        title=document.title,
        source_type=document.source_type.value,
        source_uri=document.source_uri,
        content_hash=document.content_hash,
        metadata_=document.metadata,
        status=document.status.value,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _document_from_record(record: DocumentRecord) -> Document:
    return Document(
        id=UUID(record.id),
        tenant_id=record.tenant_id,
        title=record.title,
        source_type=SourceType(record.source_type),
        source_uri=record.source_uri,
        content_hash=record.content_hash,
        metadata=record.metadata_ or {},
        status=IngestionStatus(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _chunk_to_record(chunk: DocumentChunk) -> ChunkRecord:
    return ChunkRecord(
        id=str(chunk.id),
        document_id=str(chunk.document_id),
        tenant_id=chunk.tenant_id,
        text=chunk.text,
        ordinal=chunk.ordinal,
        token_count=chunk.token_count,
        metadata_=chunk.metadata,
    )


def _chunk_from_record(record: ChunkRecord) -> DocumentChunk:
    return DocumentChunk(
        id=UUID(record.id),
        document_id=UUID(record.document_id),
        tenant_id=record.tenant_id,
        text=record.text,
        ordinal=record.ordinal,
        token_count=record.token_count,
        metadata=record.metadata_ or {},
    )


def _message_from_record(record: MessageRecord) -> ConversationMessage:
    return ConversationMessage(
        id=UUID(record.id),
        conversation_id=UUID(record.conversation_id),
        tenant_id=record.tenant_id,
        role=record.role,
        content=record.content,
        citations=[Citation.model_validate(citation) for citation in record.citations],
        created_at=record.created_at,
    )


def _job_to_record(job: IngestionJob) -> IngestionJobRecord:
    return IngestionJobRecord(
        id=str(job.id),
        tenant_id=job.tenant_id,
        job_type=job.job_type.value,
        status=job.status.value,
        source_uri=job.source_uri,
        title=job.title,
        payload=job.payload,
        content=job.content,
        document_id=str(job.document_id) if job.document_id else None,
        chunks_indexed=job.chunks_indexed,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _job_from_record(record: IngestionJobRecord) -> IngestionJob:
    return IngestionJob(
        id=UUID(record.id),
        tenant_id=record.tenant_id,
        job_type=IngestionJobType(record.job_type),
        status=IngestionJobStatus(record.status),
        source_uri=record.source_uri,
        title=record.title,
        payload=record.payload or {},
        content=record.content,
        document_id=UUID(record.document_id) if record.document_id else None,
        chunks_indexed=record.chunks_indexed,
        attempts=record.attempts,
        max_attempts=record.max_attempts,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
