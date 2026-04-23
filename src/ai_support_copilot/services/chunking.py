from collections.abc import Iterable

from ai_support_copilot.domain.models import DocumentChunk
from ai_support_copilot.services.text import estimate_tokens, normalize_text


class ChunkingEngine:
    def __init__(self, chunk_size: int = 900, overlap: int = 120) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def recursive_chunks(
        self, *, tenant_id: str, document_id, text: str, metadata: dict
    ) -> list[DocumentChunk]:
        paragraphs = [normalize_text(part) for part in text.split("\n\n") if normalize_text(part)]
        return self._pack(
            tenant_id=tenant_id, document_id=document_id, segments=paragraphs, metadata=metadata
        )

    def metadata_aware_chunks(
        self, *, tenant_id: str, document_id, text: str, metadata: dict
    ) -> list[DocumentChunk]:
        segments: list[str] = []
        current_heading = ""
        for line in text.splitlines():
            if line.strip().startswith("#"):
                current_heading = line.strip("# ").strip()
            elif line.strip():
                prefix = f"{current_heading}: " if current_heading else ""
                segments.append(prefix + line.strip())
        return self._pack(
            tenant_id=tenant_id, document_id=document_id, segments=segments, metadata=metadata
        )

    def semantic_chunks(
        self, *, tenant_id: str, document_id, text: str, metadata: dict
    ) -> list[DocumentChunk]:
        sentences = [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]
        return self._pack(
            tenant_id=tenant_id,
            document_id=document_id,
            segments=[sentence + "." for sentence in sentences],
            metadata=metadata,
        )

    def _pack(
        self, *, tenant_id: str, document_id, segments: Iterable[str], metadata: dict
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        current: list[str] = []
        current_tokens = 0
        ordinal = 0
        for segment in segments:
            segment_tokens = estimate_tokens(segment)
            if current and current_tokens + segment_tokens > self.chunk_size:
                text = " ".join(current)
                chunks.append(
                    DocumentChunk(
                        tenant_id=tenant_id,
                        document_id=document_id,
                        text=text,
                        ordinal=ordinal,
                        token_count=estimate_tokens(text),
                        metadata=metadata | {"chunk_strategy": "recursive"},
                    )
                )
                ordinal += 1
                overlap_words = " ".join(text.split()[-self.overlap :])
                current = [overlap_words] if overlap_words else []
                current_tokens = estimate_tokens(overlap_words) if overlap_words else 0
            current.append(segment)
            current_tokens += segment_tokens
        if current:
            text = " ".join(current)
            chunks.append(
                DocumentChunk(
                    tenant_id=tenant_id,
                    document_id=document_id,
                    text=text,
                    ordinal=ordinal,
                    token_count=estimate_tokens(text),
                    metadata=metadata | {"chunk_strategy": "recursive"},
                )
            )
        return chunks
