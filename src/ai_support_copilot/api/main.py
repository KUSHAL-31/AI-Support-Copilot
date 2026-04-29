from contextlib import asynccontextmanager
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ai_support_copilot.api.dependencies import Container, get_container
from ai_support_copilot.core.config import Settings, get_settings
from ai_support_copilot.core.logging import configure_logging
from ai_support_copilot.domain.models import (
    AuthenticatedUser,
    IngestionJobResponse,
    LoginRequest,
    QueryRequest,
    TokenResponse,
    UrlIngestionRequest,
    User,
    UserCreate,
)
from ai_support_copilot.observability.metrics import (
    INGESTION_COUNT,
    QUERY_LATENCY,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    prometheus_payload,
)
from ai_support_copilot.security.auth import (
    create_access_token,
    hash_password,
    require_user,
    validate_email,
    validate_password_strength,
    verify_password,
)
from ai_support_copilot.security.rate_limit import InMemoryRateLimiter

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(application: FastAPI):
    del application
    container = get_container()
    await container.startup()
    try:
        yield
    finally:
        await container.shutdown()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Enterprise-ready AI support copilot backend with pluggable RAG infrastructure.",
    lifespan=lifespan,
)
rate_limiter = InMemoryRateLimiter(settings.rate_limit_per_minute)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        with REQUEST_LATENCY.labels(request.method, request.url.path).time():
            response = await call_next(request)
        REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
        return response


app.add_middleware(MetricsMiddleware)


@app.get("/health")
async def health(container: Container = Depends(get_container)) -> dict:
    return {
        "status": "ok",
        "llm_provider": container.llm.name,
        "embedding_provider": container.embeddings.name,
        "vector_store": container.vector_store.name,
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(prometheus_payload(), media_type="text/plain; version=0.0.4")


@app.post("/auth/register", dependencies=[Depends(rate_limiter)])
async def register_user(
    request: UserCreate,
    container: Container = Depends(get_container),
    auth_settings: Settings = Depends(get_settings),
) -> TokenResponse:
    email = validate_email(request.email)
    validate_password_strength(request.password, auth_settings.auth_password_min_length)
    user = User(
        tenant_id=request.tenant_id,
        email=email,
        password_hash=hash_password(request.password),
        role=request.role,
    )
    try:
        await container.users.create(user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TokenResponse(
        access_token=create_access_token(user, auth_settings),
        expires_in=auth_settings.auth_access_token_minutes * 60,
    )


@app.post("/auth/token", dependencies=[Depends(rate_limiter)])
async def login(
    request: LoginRequest,
    container: Container = Depends(get_container),
    auth_settings: Settings = Depends(get_settings),
) -> TokenResponse:
    user = await container.users.get_by_email(validate_email(request.email))
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
        )
    return TokenResponse(
        access_token=create_access_token(user, auth_settings),
        expires_in=auth_settings.auth_access_token_minutes * 60,
    )


@app.get("/auth/me")
async def me(current_user: AuthenticatedUser = Depends(require_user)) -> AuthenticatedUser:
    return current_user


@app.post("/documents/upload", dependencies=[Depends(rate_limiter)])
async def upload_document(
    tenant_id: str | None = Form(default=None),
    file: UploadFile = File(...),
    container: Container = Depends(get_container),
    current_user: AuthenticatedUser = Depends(require_user),
) -> IngestionJobResponse:
    if tenant_id and tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="tenant mismatch")
    payload = await file.read()
    result = await container.ingestion.enqueue_file(
        tenant_id=current_user.tenant_id,
        filename=file.filename or "document.txt",
        payload=payload,
    )
    INGESTION_COUNT.labels(result.status.value).inc()
    return result


@app.post("/documents/url", dependencies=[Depends(rate_limiter)])
async def ingest_url(
    request: UrlIngestionRequest,
    container: Container = Depends(get_container),
    current_user: AuthenticatedUser = Depends(require_user),
) -> IngestionJobResponse:
    if request.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="tenant mismatch")
    result = await container.ingestion.enqueue_url(
        tenant_id=current_user.tenant_id, url=str(request.url), title=request.title
    )
    INGESTION_COUNT.labels(result.status.value).inc()
    return result


@app.get("/ingestion/jobs/{job_id}", dependencies=[Depends(rate_limiter)])
async def get_ingestion_job(
    job_id: UUID,
    container: Container = Depends(get_container),
    current_user: AuthenticatedUser = Depends(require_user),
) -> IngestionJobResponse:
    job = await container.ingestion.get_job(tenant_id=current_user.tenant_id, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ingestion job not found")
    return IngestionJobResponse(
        job_id=job.id,
        status=job.status,
        document_id=job.document_id,
        chunks_indexed=job.chunks_indexed,
        attempts=job.attempts,
        error=job.error,
    )


@app.delete("/documents/{document_id}", dependencies=[Depends(rate_limiter)])
async def delete_document(
    document_id: str,
    container: Container = Depends(get_container),
    current_user: AuthenticatedUser = Depends(require_user),
) -> dict:
    await container.ingestion.delete_document(current_user.tenant_id, UUID(document_id))
    return {"deleted": document_id}


@app.post("/query", dependencies=[Depends(rate_limiter)])
async def query(
    request: QueryRequest,
    container: Container = Depends(get_container),
    current_user: AuthenticatedUser = Depends(require_user),
):
    if request.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="tenant mismatch")
    if request.stream:

        async def chunks():
            response = await container.workflow.run(
                request.model_copy(update={"tenant_id": current_user.tenant_id})
            )
            yield response.model_dump_json()

        return StreamingResponse(chunks(), media_type="application/json")
    response = await container.workflow.run(
        request.model_copy(update={"tenant_id": current_user.tenant_id})
    )
    QUERY_LATENCY.observe(response.latency_ms)
    return response


@app.get("/conversations/{conversation_id}", dependencies=[Depends(rate_limiter)])
async def get_conversation(
    conversation_id: str,
    container: Container = Depends(get_container),
    current_user: AuthenticatedUser = Depends(require_user),
) -> dict:
    conversation = await container.conversations.get(current_user.tenant_id, UUID(conversation_id))
    if not conversation:
        raise HTTPException(status_code=404, detail="conversation not found")
    return conversation.model_dump(mode="json")


def run() -> None:
    uvicorn.run("ai_support_copilot.api.main:app", host=settings.api_host, port=settings.api_port)
