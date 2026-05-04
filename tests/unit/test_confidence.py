from uuid import uuid4

from ai_support_copilot.domain.models import Citation, DocumentChunk, RetrievalHit
from ai_support_copilot.services.confidence import ConfidenceScorer


def test_confidence_requires_retrieval_and_citations() -> None:
    scorer = ConfidenceScorer()
    assert scorer.score([], [], "answer") == 0.0


def test_confidence_scores_grounded_answer() -> None:
    scorer = ConfidenceScorer()
    chunk = DocumentChunk(
        document_id=uuid4(),
        tenant_id="acme",
        text="Rotate keys from the admin console.",
        ordinal=0,
        token_count=8,
    )
    hit = RetrievalHit(chunk=chunk, score=0.9, source="hybrid", rerank_score=0.92)
    citation = Citation(
        document_id=chunk.document_id,
        chunk_id=chunk.id,
        title="Security",
        excerpt=chunk.text,
        score=0.92,
    )

    assert scorer.score([hit], [citation], "Use admin console [1].") > 0.5
