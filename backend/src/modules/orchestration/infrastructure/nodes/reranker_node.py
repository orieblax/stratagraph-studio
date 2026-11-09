"""Node 6: Re-Ranker Node (Quantized Cross-Encoder scoring, filtering, telemetry)."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.modules.orchestration.domain.interfaces import TopologyEvent
from src.modules.orchestration.domain.state import AgentState
from src.modules.rag_etl.domain.repositories import ScoredChunk
from src.modules.rag_etl.infrastructure.reranker import QuantizedCrossEncoderReranker
from src.shared.registry import register_node

NODE_NAME = "reranker_node"


@register_node(NODE_NAME)
async def reranker_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Score candidates using quantized cross-encoder and filter below cutoff."""
    start_time = time.time()
    streamer = config.get("configurable", {}).get("streamer") if config else None
    cid = state.get("correlation_id", "")

    policy = (
        config.get("configurable", {}).get("reranker_device_policy") if config else None
    ) or "onnx-int8"

    reranker = QuantizedCrossEncoderReranker(device_policy=policy)

    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_start",
                node_id=NODE_NAME,
                status="Running",
                correlation_id=cid,
                details={"device_policy": policy},
            )
        )

    query = state.get("user_query", "")
    candidates_raw = state.get("retrieved_chunks") or []

    # Map state dicts to ScoredChunk domain models
    chunks_to_score = [
        ScoredChunk(
            chunk_id=c["chunk_id"],
            document_id=c["document_id"],
            chunk_index=c["chunk_index"],
            content=c.get("raw_content") or c["content"],
            metadata=c["metadata"],
            vector_score=c.get("vector_score", 0.0),
            bm25_score=c.get("bm25_score", 0.0),
            rrf_score=c.get("rrf_score", 0.0),
            source_backend=c.get("source_backend", "postgres_local"),
        )
        for c in candidates_raw
    ]

    scored = await reranker.rerank_chunks(query, chunks_to_score, score_cutoff=0.0)

    # Format telemetry dicts
    reranked_output: list[dict[str, Any]] = []
    for s, orig in zip(scored, candidates_raw, strict=False):
        reranked_output.append(
            {
                "chunk_id": s.chunk_id,
                "document_id": s.document_id,
                "chunk_index": s.chunk_index,
                "content": orig["content"],  # Keep spotlighted XML content
                "raw_content": s.content,
                "metadata": s.metadata,
                "vector_score": s.vector_score,
                "rrf_score": s.rrf_score,
                "rerank_score": s.rerank_score,
                "source_backend": s.source_backend,
            }
        )

    exec_ms = round((time.time() - start_time) * 1000, 2)
    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_end",
                node_id=NODE_NAME,
                status="Success",
                execution_time_ms=exec_ms,
                correlation_id=cid,
                details={
                    "candidates_scored": len(reranked_output),
                    "device_policy": policy,
                    "top_rerank_score": reranked_output[0]["rerank_score"]
                    if reranked_output
                    else 0.0,
                },
            )
        )

    return {
        "reranked_chunks": reranked_output,
        "active_route": "supervisor_router_node",
    }
