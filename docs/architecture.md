# Architecture

```mermaid
flowchart LR
  Client --> API[FastAPI Gateway]
  API --> RateLimit[Rate Limiter]
  API --> Ingestion[Ingestion Service]
  API --> Query[LangGraph Query Workflow]
  Ingestion --> Parser[PDF/DOCX/MD/TXT/URL Parser]
  Parser --> Chunker[Chunking Engine]
  Chunker --> Embeddings[Embedding Provider]
  Embeddings --> Vector[(Vector Store)]
  Query --> Rewrite[Query Rewrite]
  Rewrite --> Hybrid[Hybrid Retrieval]
  Hybrid --> Rerank[Reranker]
  Rerank --> Context[Token-Aware Context Builder]
  Context --> Generate[LLM Provider]
  Generate --> Confidence[Confidence Gate]
  API --> Metrics[Prometheus Metrics]
  API --> Postgres[(Postgres)]
  API --> Redis[(Redis Cache)]
  API --> Qdrant[(Qdrant Vector DB)]
  Worker[Ingestion Worker] --> Postgres
  Worker --> Parser
  Worker --> Embeddings
  Worker --> Qdrant
```

## Key Boundaries

- API layer owns validation, rate limiting, streaming response shape, tenant headers, and OpenAPI.
- Service layer owns ingestion, parsing, chunking, retrieval, context packing, and confidence scoring.
- Provider layer isolates LLM, embedding, reranker, and vector database implementations.
- Repository layer persists tenants, users, documents, chunks, conversations, messages, and citations
  in Postgres through SQLAlchemy async repositories.
- Ingestion jobs are durable Postgres rows. API requests enqueue jobs, and workers atomically claim
  pending jobs, process them, update retry/status fields, and write document/chunk metadata.
- Workflow layer uses LangGraph so retrieval and generation nodes can evolve into durable agent workflows.

## Multi-Tenancy

Every user, document, chunk, conversation, message, and vector search request carries `tenant_id`.
Protected API routes derive tenant authority from the JWT bearer token, not from user-controlled
headers. Qdrant uses payload filters; the in-memory test vector store filters before scoring.

## Production Follow-Ups

- Run Alembic migrations as an explicit deployment/release step before new API containers start.
- Move ingestion jobs to Celery/RabbitMQ or Kafka when throughput requires independent scaling.
- Add OpenTelemetry traces and Langfuse/LangSmith spans around provider calls.
- Add managed reranker integrations such as Cohere or a local cross-encoder model.
