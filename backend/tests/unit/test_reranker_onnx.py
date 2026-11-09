"""Unit tests for QuantizedCrossEncoderReranker and hardware VRAM policy."""

import pytest

from src.modules.rag_etl.domain.repositories import ScoredChunk
from src.modules.rag_etl.infrastructure.reranker import QuantizedCrossEncoderReranker


@pytest.fixture
def reranker() -> QuantizedCrossEncoderReranker:
    return QuantizedCrossEncoderReranker(device_policy="onnx-int8")


def test_reranker_device_policy_defaults_to_onnx_int8(
    reranker: QuantizedCrossEncoderReranker,
) -> None:
    assert reranker.device_policy == "onnx-int8"


@pytest.mark.asyncio
async def test_reranker_scores_and_sorts_chunks(
    reranker: QuantizedCrossEncoderReranker,
) -> None:
    query = "Databricks Lakehouse Vector Search indexing"
    chunks = [
        ScoredChunk(
            chunk_id="chunk_unrelated",
            document_id="doc_1",
            chunk_index=0,
            content="Baking a chocolate cake requires flour, cocoa powder, and sugar.",
            vector_score=0.88,
            rrf_score=0.015,
        ),
        ScoredChunk(
            chunk_id="chunk_highly_relevant",
            document_id="doc_2",
            chunk_index=1,
            content="Databricks Lakehouse Vector Search automatically indexes Silver Delta tables.",
            vector_score=0.85,
            rrf_score=0.012,
        ),
    ]

    results = await reranker.rerank_chunks(query, chunks, score_cutoff=0.0)

    assert len(results) == 2
    # Highly relevant chunk should have a higher Cross-Encoder score and be ranked first
    assert results[0].chunk_id == "chunk_highly_relevant"
    assert results[0].rerank_score is not None
    assert results[1].rerank_score is not None
    assert results[0].rerank_score > results[1].rerank_score

    # Original vector score is preserved for UI comparison
    assert results[0].vector_score == 0.85


@pytest.mark.asyncio
async def test_reranker_filters_below_score_cutoff(
    reranker: QuantizedCrossEncoderReranker,
) -> None:
    query = "Postgres pgvector HNSW index performance"
    chunks = [
        ScoredChunk(
            chunk_id="chunk_noise",
            document_id="doc_noise",
            chunk_index=0,
            content="Completely irrelevant text about outer space galaxies and stars.",
            vector_score=0.70,
        )
    ]

    # Filter with strict cutoff
    results = await reranker.rerank_chunks(query, chunks, score_cutoff=0.60)
    assert len(results) == 0
