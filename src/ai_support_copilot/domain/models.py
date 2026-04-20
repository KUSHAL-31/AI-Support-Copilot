from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class IngestionStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class IngestionJobStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class IngestionJobType(StrEnum):
    file = "file"
    url = "url"


class SourceType(StrEnum):
    pdf = "pdf"
    docx = "docx"
    markdown = "markdown"
    text = "text"
    url = "url"


class Document(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    title: str
    source_type: SourceType
    source_uri: str | None = None
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: IngestionStatus = IngestionStatus.pending
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DocumentChunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    tenant_id: str
    text: str
    ordinal: int
    token_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbeddedChunk(DocumentChunk):
    embedding: list[float]


class RetrievalHit(BaseModel):
    chunk: DocumentChunk
    score: float
    source: str
    rerank_score: float | None = None


class Citation(BaseModel):
    document_id: UUID
    chunk_id: UUID
    title: str
    source_uri: str | None = None
    excerpt: str
    score: float


class QueryRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    stream: bool = False
    top_k: int = Field(default=8, ge=1, le=30)
    filters: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    conversation_id: UUID
    answer: str
    confidence: float
    citations: list[Citation]
    rewritten_query: str
    latency_ms: float
    cached: bool = False


class UploadResponse(BaseModel):
    document_id: UUID
    status: IngestionStatus
    chunks_indexed: int = 0


class IngestionJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    job_type: IngestionJobType
    status: IngestionJobStatus = IngestionJobStatus.pending
    source_uri: str
    title: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    content: bytes | None = None
    document_id: UUID | None = None
    chunks_indexed: int = 0
    attempts: int = 0
    max_attempts: int = 3
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IngestionJobResponse(BaseModel):
    job_id: UUID
    status: IngestionJobStatus
    document_id: UUID | None = None
    chunks_indexed: int = 0
    attempts: int = 0
    error: str | None = None


class UrlIngestionRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    title: str | None = None


class ConversationMessage(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    tenant_id: str
    role: str
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Conversation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    messages: list[ConversationMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserRole(StrEnum):
    admin = "admin"
    member = "member"


class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    email: str
    password_hash: str
    role: UserRole = UserRole.member
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserCreate(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    role: UserRole = UserRole.admin


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthenticatedUser(BaseModel):
    id: UUID
    tenant_id: str
    email: str
    role: UserRole
