from ai_support_copilot.domain.models import Citation, RetrievalHit


class ConfidenceScorer:
    def score(self, hits: list[RetrievalHit], citations: list[Citation], answer: str) -> float:
        if not hits or not citations:
            return 0.0
        retrieval = max((hit.rerank_score or hit.score for hit in hits), default=0.0)
        citation_density = min(1.0, len(citations) / 4)
        grounding = 0.2 if "could not find reliable information" in answer.lower() else 0.8
        return round(
            max(0.0, min(1.0, 0.5 * retrieval + 0.3 * citation_density + 0.2 * grounding)), 3
        )
