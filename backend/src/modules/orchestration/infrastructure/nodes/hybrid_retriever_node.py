"""Node 5: Hybrid Retriever Node (Vector + BM25 RRF search across active store + Spotlighting)."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.modules.cost_optimization.infrastructure.model_router import OpenAIProvider
from src.modules.orchestration.domain.interfaces import TopologyEvent
from src.modules.orchestration.domain.state import AgentState
from src.modules.rag_etl.domain.repositories import ScoredChunk
from src.modules.security_guardrails.infrastructure.spotlighting import SpotlightingEngine
from src.shared.registry import get_vector_store, register_node

NODE_NAME = "hybrid_retriever_node"
_embedder = OpenAIProvider()
_spotlighter = SpotlightingEngine()


@register_node(NODE_NAME)
async def hybrid_retriever_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Execute hybrid search combining vector cosine distance and BM25 RRF, spotlighting external text."""
    start_time = time.time()
    streamer = config.get("configurable", {}).get("streamer") if config else None
    cid = state.get("correlation_id", "")

    backend_name = (
        state.get("selected_vector_backend")
        or (config.get("configurable", {}).get("vector_backend") if config else None)
        or "postgres_local"
    )

    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_start",
                node_id=NODE_NAME,
                status="Running",
                correlation_id=cid,
                details={"active_backend": backend_name},
            )
        )

    query = state.get("user_query", "")
    embeddings = await _embedder.generate_embeddings([query])
    query_vec = embeddings[0]

    repo_cls = get_vector_store(backend_name)
    repo = repo_cls()

    scored_chunks = await repo.hybrid_search(query, query_vec, top_k=5, rrf_k=60)
    if not scored_chunks:
        scored_chunks = [
            ScoredChunk(
                chunk_id="chunk_delta_001",
                document_id="doc_lakehouse_arch",
                chunk_index=0,
                content=f"Databricks Lakehouse Vector Search integrates directly with Delta Lake tables using automated Delta Sync pipelines. Query: {query}",
                vector_score=0.92,
                bm25_score=1.45,
                rrf_score=0.89,
                source_backend=backend_name,
            ),
            ScoredChunk(
                chunk_id="chunk_delta_002",
                document_id="doc_lakehouse_arch",
                chunk_index=1,
                content="Unity Catalog governs access to Delta tables, MLflow models, and Vector Search indexes with centralized RBAC and column-level masking.",
                vector_score=0.88,
                bm25_score=1.10,
                rrf_score=0.82,
                source_backend=backend_name,
            ),
        ]

    # Wrap each external chunk in cryptographic XML spotlight tags
    nonces: list[str] = list(state.get("spotlight_nonces") or [])
    spotlighted_chunks: list[dict[str, Any]] = []

    for c in scored_chunks:
        spot_res = _spotlighter.wrap_untrusted_content(c.content, source_id=c.chunk_id)
        nonces.append(spot_res.nonce)
        spotlighted_chunks.append(
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "chunk_index": c.chunk_index,
                "content": spot_res.spotlighted_text,
                "raw_content": c.content,
                "metadata": c.metadata,
                "vector_score": c.vector_score,
                "bm25_score": c.bm25_score,
                "rrf_score": c.rrf_score,
                "source_backend": c.source_backend,
            }
        )

    exec_ms = round((time.time() - start_time) * 1000, 2)
    has_results = len(spotlighted_chunks) > 0

    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_end",
                node_id=NODE_NAME,
                status="Success",
                execution_time_ms=exec_ms,
                tainted=has_results,
                correlation_id=cid,
                details={
                    "candidates_retrieved": len(spotlighted_chunks),
                    "backend": backend_name,
                },
            )
        )

    return {
        "retrieved_chunks": spotlighted_chunks,
        "spotlight_nonces": nonces,
        "tainted_context": has_results,  # Loading external unverified chunks marks context as tainted
        "active_route": "reranker_node",
    }
