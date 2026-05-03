from time import perf_counter

from pydantic import BaseModel, Field

from ai_support_copilot.core.config import Settings
from ai_support_copilot.domain.models import (
    ConversationMessage,
    QueryRequest,
    QueryResponse,
    RetrievalHit,
)
from ai_support_copilot.providers.protocols import LLMProvider, Reranker
from ai_support_copilot.repositories.cache import AsyncTTLCache
from ai_support_copilot.repositories.conversations import ConversationRepository
from ai_support_copilot.security.prompt_guard import has_prompt_injection
from ai_support_copilot.services.confidence import ConfidenceScorer
from ai_support_copilot.services.context import ContextBuilder
from ai_support_copilot.services.retrieval import HybridRetrievalService
from ai_support_copilot.services.text import sanitize_user_text


class QueryState(BaseModel):
    request: QueryRequest
    conversation_id: str | None = None
    rewritten_query: str = ""
    hits: list[RetrievalHit] = Field(default_factory=list)
    context: str = ""
    answer: str = ""
    confidence: float = 0.0


class QueryWorkflow:
    def __init__(
        self,
        *,
        settings: Settings,
        llm: LLMProvider,
        retrieval: HybridRetrievalService,
        reranker: Reranker,
        context_builder: ContextBuilder,
        confidence: ConfidenceScorer,
        conversations: ConversationRepository,
        cache: AsyncTTLCache,
    ) -> None:
        self._settings = settings
        self._llm = llm
        self._retrieval = retrieval
        self._reranker = reranker
        self._context_builder = context_builder
        self._confidence = confidence
        self._conversations = conversations
        self._cache = cache
        self.graph = self._compile_graph()

    async def run(self, request: QueryRequest) -> QueryResponse:
        start = perf_counter()
        query = sanitize_user_text(request.query)
        cache_key = self._cache.key(request.tenant_id, query, str(request.filters))
        cached = await self._cache.get_json(cache_key)
        if cached:
            response = QueryResponse.model_validate(cached)
            return response.model_copy(update={"cached": True})

        conversation = await self._conversations.get_or_create(
            request.tenant_id, request.conversation_id
        )
        await self._conversations.append(
            ConversationMessage(
                conversation_id=conversation.id,
                tenant_id=request.tenant_id,
                role="user",
                content=query,
            )
        )
        rewritten = await self._rewrite(query)
        graph_state = await self.graph.ainvoke(
            {
                "request": request,
                "query": query,
                "rewritten_query": rewritten,
                "hits": [],
                "context": "",
                "citations": [],
                "answer": "",
            }
        )
        reranked = graph_state["hits"]
        citations = graph_state["citations"]
        answer = graph_state["answer"]
        score = self._confidence.score(reranked, citations, answer)
        if has_prompt_injection(query) or score < self._settings.confidence_threshold:
            answer = "I could not find reliable information in the knowledge base."
            citations = []
            score = min(score, self._settings.confidence_threshold)
        response = QueryResponse(
            conversation_id=conversation.id,
            answer=answer,
            confidence=score,
            citations=citations,
            rewritten_query=rewritten,
            latency_ms=round((perf_counter() - start) * 1000, 2),
        )
        await self._conversations.append(
            ConversationMessage(
                conversation_id=conversation.id,
                tenant_id=request.tenant_id,
                role="assistant",
                content=response.answer,
                citations=response.citations,
            )
        )
        await self._cache.set_json(cache_key, response.model_dump(mode="json"), ttl_seconds=300)
        return response

    def _compile_graph(self):
        from langgraph.graph import END, StateGraph

        graph = StateGraph(dict)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("rerank", self._rerank_node)
        graph.add_node("build_context", self._context_node)
        graph.add_node("generate", self._generate_node)
        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "rerank")
        graph.add_edge("rerank", "build_context")
        graph.add_edge("build_context", "generate")
        graph.add_edge("generate", END)
        return graph.compile()

    async def _retrieve_node(self, state: dict) -> dict:
        request: QueryRequest = state["request"]
        state["hits"] = await self._retrieval.retrieve(
            tenant_id=request.tenant_id,
            query=state["rewritten_query"],
            top_k=max(request.top_k, self._settings.retrieval_top_k),
            filters=request.filters,
        )
        return state

    async def _rerank_node(self, state: dict) -> dict:
        request: QueryRequest = state["request"]
        state["hits"] = await self._reranker.rerank(
            state["rewritten_query"],
            state["hits"],
            top_k=min(request.top_k, self._settings.rerank_top_k),
        )
        return state

    async def _context_node(self, state: dict) -> dict:
        context, citations = self._context_builder.build(state["hits"])
        state["context"] = context
        state["citations"] = citations
        return state

    async def _generate_node(self, state: dict) -> dict:
        state["answer"] = await self._generate(
            query=state["query"], context=state["context"], low_context=not state["citations"]
        )
        return state

    async def _rewrite(self, query: str) -> str:
        prompt = (
            "Rewrite the user query for enterprise knowledge-base retrieval. "
            "Keep product names, incidents, dates, and error codes intact.\n"
            f"Query: {query}"
        )
        rewritten = await self._llm.complete(prompt)
        return sanitize_user_text(rewritten or query)

    async def _generate(self, *, query: str, context: str, low_context: bool) -> str:
        if low_context:
            return "I could not find reliable information in the knowledge base."
        prompt = f"""
You are an enterprise support copilot. Answer only from the provided context.
If the answer is not supported, say: I could not find reliable information in the knowledge base.
Use concise operational language and cite sources by bracket number.

Context:
{context}

Question:
{query}
"""
        return await self._llm.complete(prompt, temperature=0.0)
