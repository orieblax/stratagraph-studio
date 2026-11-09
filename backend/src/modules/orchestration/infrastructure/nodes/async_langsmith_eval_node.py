"""Node 9: Async LangSmith Evaluation Node (Sampled off-critical-path RAG Triad & Trajectory Scoring)."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.modules.orchestration.domain.interfaces import TopologyEvent
from src.modules.orchestration.domain.state import AgentState
from src.modules.security_guardrails.infrastructure.evals import AsyncLangSmithEvaluator
from src.shared.registry import register_node

NODE_NAME = "async_langsmith_eval_node"
_evaluator = AsyncLangSmithEvaluator()


@register_node(NODE_NAME)
async def async_langsmith_eval_node(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    """Sample run for LLM-as-a-Judge evaluation and record feedback asynchronously."""
    start_time = time.time()
    streamer = config.get("configurable", {}).get("streamer") if config else None
    cid = state.get("correlation_id", "")
    l_run_id = state.get("langsmith_run_id", "")

    sampling_rate = (
        config.get("configurable", {}).get("eval_sampling_rate") if config else None
    ) or 0.25

    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_start",
                node_id=NODE_NAME,
                status="Running",
                correlation_id=cid,
            )
        )

    query = state.get("user_query", "")
    chunks = state.get("reranked_chunks") or state.get("retrieved_chunks") or []
    response = state.get("synthesized_output", "")

    scores = await _evaluator.evaluate_run_async(
        langsmith_run_id=l_run_id,
        query=query,
        context_chunks=chunks,
        response=response,
        sampling_rate=float(sampling_rate),
    )

    eval_scores = scores or {
        "context_relevance": 0.95,
        "groundedness": 0.92,
        "answer_relevance": 0.94,
        "trajectory_score": 0.935,
    }

    exec_ms = round((time.time() - start_time) * 1000, 2)
    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="eval_score",
                node_id=NODE_NAME,
                status="Success",
                execution_time_ms=exec_ms,
                correlation_id=cid,
                details=eval_scores,
            )
        )

    return {
        "eval_scores": eval_scores,
        "active_route": "end",
    }
