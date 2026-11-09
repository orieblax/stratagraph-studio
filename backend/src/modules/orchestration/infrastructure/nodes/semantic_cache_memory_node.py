"""Node 2: Semantic Cache & Checkpoint Memory Node (Tier-1 exact & Tier-2 pgvector lookup)."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.modules.cost_optimization.infrastructure.model_router import OpenAIProvider
from src.modules.cost_optimization.infrastructure.semantic_cache import TwoTierPgVectorCache
from src.modules.orchestration.domain.interfaces import TopologyEvent
from src.modules.orchestration.domain.state import AgentState
from src.shared.registry import register_node

NODE_NAME = "semantic_cache_memory_node"
_cache = TwoTierPgVectorCache()
_embedder = OpenAIProvider()


@register_node(NODE_NAME)
async def semantic_cache_memory_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Check Tier 1 exact match and Tier 2 pgvector cosine similarity."""
    start_time = time.time()
    streamer = config.get("configurable", {}).get("streamer") if config else None
    cid = state.get("correlation_id", "")
    cfg_hash = state.get("config_hash", "default_config")

    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_start",
                node_id=NODE_NAME,
                status="Running",
                correlation_id=cid,
            )
        )

    # If semantic cache is disabled in config, bypass directly to router
    cache_enabled = (
        config.get("configurable", {}).get("semantic_cache_enabled", True) if config else True
    )
    threshold = (
        config.get("configurable", {}).get("semantic_cache_threshold", 0.92) if config else 0.92
    )

    query = state.get("user_query", "")
    if not cache_enabled or not query:
        exec_ms = round((time.time() - start_time) * 1000, 2)
        if streamer:
            await streamer.emit_topology(
                TopologyEvent(
                    event_type="node_end",
                    node_id=NODE_NAME,
                    status="Success",
                    execution_time_ms=exec_ms,
                    correlation_id=cid,
                    details={"cache_enabled": False},
                )
            )
        return {
            "cache_hit": False,
            "active_route": "supervisor_router_node",
        }

    # Generate query embedding for Tier 2 lookup
    embeddings = await _embedder.generate_embeddings([query])
    query_vec = embeddings[0]

    cache_res = await _cache.get(query, query_vec, cfg_hash, threshold=threshold)
    exec_ms = round((time.time() - start_time) * 1000, 2)

    if cache_res.hit:
        if streamer:
            await streamer.emit_topology(
                TopologyEvent(
                    event_type="node_end",
                    node_id=NODE_NAME,
                    status="Cache Hit",
                    execution_time_ms=exec_ms,
                    micro_cost_usd=0.0,
                    correlation_id=cid,
                    details={
                        "tier": cache_res.tier,
                        "similarity_score": cache_res.similarity_score,
                    },
                )
            )
        return {
            "cache_hit": True,
            "cache_tier": cache_res.tier,
            "cached_response": cache_res.cached_response,
            "synthesized_output": cache_res.cached_response or "",
            "active_route": "synthesis_output_guardrail_node",
        }

    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_end",
                node_id=NODE_NAME,
                status="Success",
                execution_time_ms=exec_ms,
                correlation_id=cid,
                details={"cache_hit": False},
            )
        )

    return {
        "cache_hit": False,
        "cache_tier": None,
        "cached_response": None,
        "active_route": "supervisor_router_node",
    }
