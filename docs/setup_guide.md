# Local Setup and End-to-End Guide

This guide starts from a fresh machine and gets the copilot running locally with Ollama and Qdrant.
It also explains which API keys are needed for deployment.

## 1. What Is Fully Runnable Today

The local stack is configured for:

- FastAPI backend
- LangGraph query workflow
- Local deterministic embeddings for offline development
- Ollama chat generation
- Qdrant vector database
- Redis and Postgres service containers
- Postgres persistence for tenants, users, documents, chunks, conversations, messages, and citations
- Prometheus and Grafana
- File upload ingestion
- URL ingestion
- Hybrid retrieval
- Reranking
- Citations
- Confidence fallback
- Conversation history
- JWT bearer authentication
- Tenant isolation from authenticated identity
- Durable Postgres-backed ingestion queue with worker processing

Provider abstractions exist for swapping LLM, embedding, reranker, and vector database layers. Qdrant,
Ollama, local embeddings, fake LLM, OpenAI-compatible chat providers, Postgres repositories, Qdrant,
and the in-memory test vector store are implemented. Pinecone, Weaviate, Chroma, pgvector,
Anthropic-native chat, and managed embedding providers are currently documented extension points unless
their adapters are added.

## 2. Install Prerequisites

Install:

- Python 3.12+
- PDM
- Docker Desktop
- Ollama, if you want to run Ollama outside Docker

PDM:

```bash
python3 -m pip install --user pdm
```

If `pdm` is not on your PATH, use the full path shown by pip or add this to your shell config:

```bash
export PATH="$HOME/Library/Python/3.11/bin:$PATH"
```

## 3. Create Environment File

```bash
cp .env.example .env
```

For a fully local Docker setup, keep:

```bash
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_EMBEDDING_PROVIDER=local
DEFAULT_VECTORSTORE=qdrant
OLLAMA_BASE_URL=http://ollama:11434
QDRANT_URL=http://qdrant:6333
```

For local development without Docker networking, use:

```bash
OLLAMA_BASE_URL=http://localhost:11434
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379/0
```

The API runs Alembic migrations at startup when `AUTO_RUN_MIGRATIONS=true`. For production, a safer
deployment pattern is to run migrations as a release step before starting new API containers:

```bash
pdm run migrate
```

## 4. Start the Local Infrastructure

Start the full stack:

```bash
docker compose up --build
```

Services:

- API: `http://localhost:8000`
- Worker: `worker` service in Docker Compose
- Swagger UI: `http://localhost:8000/docs`
- Qdrant: `http://localhost:6333/dashboard`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## 5. Pull Ollama Models

If using the Docker Ollama service:

```bash
docker compose exec ollama ollama pull llama3.1
docker compose exec ollama ollama pull nomic-embed-text
```

If using Ollama installed directly on your machine:

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
ollama serve
```

The current app uses Ollama for chat when `DEFAULT_LLM_PROVIDER=ollama`. Embeddings default to the
offline local embedding provider so you can test without model latency. To use Ollama embeddings,
set:

```bash
DEFAULT_EMBEDDING_PROVIDER=ollama
```

## 6. Install Python Dependencies for Local Development

```bash
pdm install -G dev
```

Run tests:

```bash
pdm run test
pdm run lint
```

Start only the API locally:

```bash
pdm run uvicorn ai_support_copilot.api.main:app --host 127.0.0.1 --port 8000
```

`pdm run dev` uses the reload watcher. If macOS blocks file watching, use the `uvicorn` command above.

## 7. End-to-End Smoke Test

Health check:

```bash
curl -s http://127.0.0.1:8000/health
```

Expected shape:

```json
{
  "status": "ok",
  "llm_provider": "ollama",
  "embedding_provider": "local",
  "vector_store": "qdrant"
}
```

Register a local tenant admin and store the token:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"acme","email":"admin@acme.test","password":"VerySecurePassword123!"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
```

Verify the token:

```bash
curl -s http://127.0.0.1:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

Upload the sample runbook:

```bash
JOB_ID=$(curl -s -H "Authorization: Bearer $TOKEN" \
  -F tenant_id=acme -F file=@examples/data/acme_runbook.md \
  http://127.0.0.1:8000/documents/upload \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')
```

The API only enqueues ingestion. The worker service processes the job. Poll status:

```bash
curl -s http://127.0.0.1:8000/ingestion/jobs/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"
```

Ask a grounded question:

```bash
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"acme","query":"Why are enterprise card payments failing?","top_k":6}'
```

Ask about key rotation:

```bash
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"acme","query":"How do we rotate API keys?","top_k":6}'
```

Test tenant isolation:

```bash
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"other","query":"How do we rotate API keys?","top_k":6}'
```

The `other` tenant request should return `403` because the tenant in the request does not match the
tenant in the signed token.

## 8. Test URL Ingestion

```bash
URL_JOB_ID=$(curl -s -X POST http://127.0.0.1:8000/documents/url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"acme","url":"https://example.com","title":"Example Page"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')
```

Poll the URL ingestion job:

```bash
curl -s http://127.0.0.1:8000/ingestion/jobs/$URL_JOB_ID \
  -H "Authorization: Bearer $TOKEN"
```

Then query the same tenant.

## 9. Test Conversations

The `/query` response includes `conversation_id`. Use it here:

```bash
curl -s http://127.0.0.1:8000/conversations/<conversation_id> \
  -H "Authorization: Bearer $TOKEN"
```

## 10. Test Metrics

```bash
curl -s http://127.0.0.1:8000/metrics
```

Prometheus should scrape the same endpoint when Docker Compose is running.

## 11. API Keys for Deployment

You do not need API keys for the default local fake/local flow. You need keys only when enabling
hosted providers.

For production authentication, set a strong signing secret. Do not use the example value:

```bash
AUTH_JWT_SECRET=$(openssl rand -base64 32)
AUTH_ACCESS_TOKEN_MINUTES=30
AUTH_PASSWORD_MIN_LENGTH=12
```

Set these in `.env` or your deployment secret manager:

```bash
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small

ANTHROPIC_API_KEY=
ANTHROPIC_CHAT_MODEL=claude-3-5-sonnet-latest

OPENROUTER_API_KEY=
OPENROUTER_CHAT_MODEL=openai/gpt-4o-mini

GROQ_API_KEY=
GROQ_CHAT_MODEL=llama-3.1-70b-versatile

PINECONE_API_KEY=
PINECONE_INDEX=
WEAVIATE_URL=
WEAVIATE_API_KEY=
```

Current provider status:

| Provider | Config Present | Adapter Status |
| --- | --- | --- |
| Ollama chat | Yes | Implemented |
| Ollama embeddings | Yes | Implemented |
| Fake/local chat | No key needed | Implemented |
| Local hash embeddings | No key needed | Implemented |
| OpenAI chat | Yes | Implemented via OpenAI-compatible endpoint |
| OpenRouter chat | Yes | Implemented via OpenAI-compatible endpoint |
| Groq chat | Yes | Implemented via OpenAI-compatible endpoint |
| Anthropic chat | Yes | Extension point |
| OpenAI embeddings | Yes | Extension point |
| Qdrant | Yes | Implemented |
| In-memory vector store | No key needed | Implemented for tests/dev |
| Postgres repositories | Yes | Implemented |
| pgvector | DSN present through Postgres | Extension point for vector search |
| Pinecone | Yes | Extension point |
| Weaviate | Yes | Extension point |
| Chroma | Host/port present | Extension point |

For a resume project, this now has real persistence in the core backend path. Before production, add
Alembic migrations and any managed provider adapters you plan to advertise as production-ready.

## 12. Recommended Local Testing Matrix

Run these combinations:

```bash
# Fast, no external model
DEFAULT_LLM_PROVIDER=fake
DEFAULT_EMBEDDING_PROVIDER=local
DEFAULT_VECTORSTORE=memory

# Local RAG with Qdrant, no hosted API keys
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_EMBEDDING_PROVIDER=local
DEFAULT_VECTORSTORE=qdrant

# Fully local model stack
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_EMBEDDING_PROVIDER=ollama
DEFAULT_VECTORSTORE=qdrant
```

After each change:

```bash
pdm run test
curl -s http://127.0.0.1:8000/health
```

## 13. Troubleshooting

If `pdm run dev` fails with a file watcher permission error:

```bash
pdm run uvicorn ai_support_copilot.api.main:app --host 127.0.0.1 --port 8000
```

If Ollama calls fail inside Docker:

```bash
docker compose logs ollama
docker compose exec ollama ollama list
```

If Qdrant search fails:

```bash
curl http://localhost:6333/collections
```

If answers always fall back, lower the threshold temporarily:

```bash
CONFIDENCE_THRESHOLD=0.3
```

Then inspect citations and retrieval scores in the `/query` response.

If ingestion jobs remain pending:

```bash
docker compose logs worker
docker compose exec api pdm run migrate
```

For local non-Docker development, run a worker in a second terminal:

```bash
pdm run worker
```
