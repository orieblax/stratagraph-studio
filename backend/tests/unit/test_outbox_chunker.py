"""Unit tests for IdempotentOutboxChunker and SHA-256 chunk deduplication."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.rag_etl.infrastructure.chunker_outbox import (
    IdempotentOutboxChunker,
    compute_chunk_hash,
)


def test_chunk_hash_computation_deterministic() -> None:
    text_a = "Strategic enterprise Lakehouse data architecture."
    text_b = "Strategic enterprise Lakehouse data architecture."
    text_c = "Different content entirely."

    hash_a = compute_chunk_hash(text_a)
    hash_b = compute_chunk_hash(text_b)
    hash_c = compute_chunk_hash(text_c)

    assert hash_a == hash_b
    assert hash_a != hash_c
    assert len(hash_a) == 64


def test_text_splitting_logic() -> None:
    chunker = IdempotentOutboxChunker(
        vector_repo=MagicMock(),
        embedding_provider=MagicMock(),
        session_factory=MagicMock(),
    )
    long_text = "Word " * 200
    chunks = chunker.split_text(long_text, chunk_size=200, chunk_overlap=20)

    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 200


@pytest.mark.asyncio
async def test_idempotent_chunker_skips_existing_embeddings() -> None:
    # Mocks
    mock_vector_repo = AsyncMock()
    mock_vector_repo.upsert_chunks.return_value = ["chunk_id_1", "chunk_id_2"]

    mock_embedding_provider = AsyncMock()
    # If text is already embedded, generate_embeddings should only be called for NEW chunks
    mock_embedding_provider.generate_embeddings.return_value = [[0.1] * 1536]

    # Session mock
    mock_session = AsyncMock()
    mock_session.begin = MagicMock()
    mock_session.begin.return_value.__aenter__ = AsyncMock()
    mock_session.begin.return_value.__aexit__ = AsyncMock()
    mock_res = MagicMock()

    session_maker = MagicMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    chunker = IdempotentOutboxChunker(
        vector_repo=mock_vector_repo,
        embedding_provider=mock_embedding_provider,
        session_factory=session_maker,
    )

    raw_doc = (
        "Chunk 1 content that is already indexed in database. "
        "Chunk 2 content that is completely novel and requires new embeddings."
    )
    # Pre-calculate chunk 1 hash as produced by chunker and pretend it already exists in database
    first_chunk = chunker.split_text(raw_doc, 100, 10)[0]
    existing_hash = compute_chunk_hash(first_chunk)

    mock_res.scalars.return_value.all.return_value = [existing_hash]
    mock_session.execute.return_value = mock_res

    inserted_ids = await chunker.process_document_etl(
        outbox_id="00000000-0000-0000-0000-000000000001",
        document_id="doc_test_101",
        raw_text=raw_doc,
        chunk_size=100,
        chunk_overlap=10,
    )

    assert len(inserted_ids) == 2
    assert mock_vector_repo.upsert_chunks.called
    # Embedding generation should be invoked for only the 1 novel chunk, not both
    assert mock_embedding_provider.generate_embeddings.call_count == 1
    call_args = mock_embedding_provider.generate_embeddings.call_args[0][0]
    assert len(call_args) == 1
