from uuid import uuid4

from ai_support_copilot.services.chunking import ChunkingEngine


def test_recursive_chunking_preserves_metadata_and_order() -> None:
    chunker = ChunkingEngine(chunk_size=20, overlap=3)
    chunks = chunker.recursive_chunks(
        tenant_id="acme",
        document_id=uuid4(),
        text="First section explains card failures.\n\nSecond section explains retries.",
        metadata={"title": "Runbook"},
    )

    assert chunks
    assert chunks[0].tenant_id == "acme"
    assert chunks[0].metadata["title"] == "Runbook"
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))
