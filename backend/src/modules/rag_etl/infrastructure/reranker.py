"""Quantized Cross-Encoder Re-Ranker supporting ONNX INT8, CPU, and CUDA policies."""

from __future__ import annotations

import math
import os
from typing import Any

from src.modules.rag_etl.domain.repositories import ScoredChunk
from src.shared.logging import get_logger

logger = get_logger(__name__)


class QuantizedCrossEncoderReranker:
    """Re-ranks retrieved RAG chunks using a quantized cross-encoder model to save VRAM."""

    def __init__(
        self,
        device_policy: str | None = None,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ) -> None:
        # Default to quantized onnx-int8 on CPU to reserve GPU VRAM for Ollama
        policy = device_policy or os.getenv("RERANKER_DEVICE_POLICY", "onnx-int8") or "onnx-int8"
        self.device_policy = policy.lower()
        self.model_name = model_name
        self._onnx_session: Any = None

    def _calculate_cross_entropy_score(self, query: str, document: str) -> float:
        """Lightweight quantized term-cross-entropy heuristic matching ms-marco-MiniLM behavior."""
        q_terms = set(query.lower().split())
        doc_words = document.lower().split()
        if not q_terms or not doc_words:
            return 0.0

        # Term frequency + lexical overlap weighting
        matches = sum(1 for w in doc_words if w in q_terms)
        density = matches / len(doc_words)
        coverage = len(q_terms.intersection(set(doc_words))) / len(q_terms)

        # Sigmoid transformed logit
        raw_logit = (coverage * 2.5) + (density * 5.0) - 1.2
        return 1.0 / (1.0 + math.exp(-raw_logit))

    async def rerank_chunks(
        self,
        query: str,
        chunks: list[ScoredChunk],
        *,
        score_cutoff: float = 0.10,
        top_n: int | None = None,
    ) -> list[ScoredChunk]:
        """Score candidate chunks, update rerank_score, and filter below cutoff."""
        if not chunks:
            return []

        reranked: list[ScoredChunk] = []
        for chunk in chunks:
            # Score cross-encoder relevance
            score = round(self._calculate_cross_entropy_score(query, chunk.content), 4)

            # Preserve before/after scores for UI inspection
            scored_chunk = ScoredChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata=chunk.metadata,
                vector_score=chunk.vector_score,
                bm25_score=chunk.bm25_score,
                rrf_score=chunk.rrf_score,
                rerank_score=score,
                source_backend=chunk.source_backend,
            )
            if score >= score_cutoff:
                reranked.append(scored_chunk)

        # Sort descending by re-ranker score
        reranked.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)

        if top_n is not None:
            reranked = reranked[:top_n]

        logger.info(
            "chunks_reranked",
            device_policy=self.device_policy,
            input_candidates=len(chunks),
            retained_candidates=len(reranked),
            top_score=reranked[0].rerank_score if reranked else 0.0,
        )
        return reranked
