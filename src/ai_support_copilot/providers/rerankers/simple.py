from collections.abc import Sequence

from ai_support_copilot.domain.models import RetrievalHit


class LexicalReranker:
    name = "lexical"

    async def rerank(
        self, query: str, hits: Sequence[RetrievalHit], *, top_k: int
    ) -> list[RetrievalHit]:
        query_terms = set(query.lower().split())
        reranked: list[RetrievalHit] = []
        for hit in hits:
            terms = set(hit.chunk.text.lower().split())
            overlap = len(query_terms & terms) / max(len(query_terms), 1)
            hit.rerank_score = min(1.0, 0.65 * hit.score + 0.35 * overlap)
            reranked.append(hit)
        return sorted(
            reranked,
            key=lambda item: item.rerank_score or item.score,
            reverse=True,
        )[:top_k]
