from ai_support_copilot.domain.models import Citation, RetrievalHit
from ai_support_copilot.security.prompt_guard import neutralize_context
from ai_support_copilot.services.text import estimate_tokens


class ContextBuilder:
    def __init__(self, max_tokens: int) -> None:
        self._max_tokens = max_tokens

    def build(self, hits: list[RetrievalHit]) -> tuple[str, list[Citation]]:
        budget = self._max_tokens
        parts: list[str] = []
        citations: list[Citation] = []
        seen: set[str] = set()
        for index, hit in enumerate(hits, start=1):
            fingerprint = hit.chunk.text[:160]
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            tokens = estimate_tokens(hit.chunk.text)
            if tokens > budget:
                continue
            budget -= tokens
            title = str(hit.chunk.metadata.get("title") or hit.chunk.document_id)
            source_uri = hit.chunk.metadata.get("source_uri")
            parts.append(f"[{index}] {neutralize_context(hit.chunk.text)}")
            citations.append(
                Citation(
                    document_id=hit.chunk.document_id,
                    chunk_id=hit.chunk.id,
                    title=title,
                    source_uri=str(source_uri) if source_uri else None,
                    excerpt=hit.chunk.text[:280],
                    score=hit.rerank_score or hit.score,
                )
            )
        return "\n\n".join(parts), citations
