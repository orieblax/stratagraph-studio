"""Node 1: Input Guardrail Node (PII masking, injection detection, budget init)."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.modules.orchestration.domain.interfaces import TopologyEvent
from src.modules.orchestration.domain.state import AgentState
from src.modules.security_guardrails.infrastructure.pii_scrubber import PIIScrubber
from src.modules.security_guardrails.infrastructure.spotlighting import _INJECTION_PATTERNS
from src.shared.registry import register_node

NODE_NAME = "input_guardrail_node"
_pii_scrubber = PIIScrubber()


@register_node(NODE_NAME)
async def input_guardrail_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Scrub PII from user query, verify prompt safety, and initialize budget metrics."""
    start_time = time.time()
    streamer = config.get("configurable", {}).get("streamer") if config else None
    cid = state.get("correlation_id", "")

    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_start",
                node_id=NODE_NAME,
                status="Running",
                correlation_id=cid,
            )
        )

    raw_query = state.get("user_query") or (
        state["messages"][-1]["content"] if state.get("messages") else ""
    )

    # 1. PII Scrubbing
    scrubbed_query = _pii_scrubber.scrub_text(raw_query)

    # 2. Injection Pattern Detection
    detected_violations: list[str] = list(state.get("security_violations") or [])
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(raw_query):
            detected_violations.append(f"Prompt Injection Pattern: {pattern.pattern}")

    exec_ms = round((time.time() - start_time) * 1000, 2)
    is_tainted = len(detected_violations) > 0

    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_end",
                node_id=NODE_NAME,
                status="Blocked by Guardrail" if is_tainted else "Success",
                execution_time_ms=exec_ms,
                tainted=is_tainted,
                correlation_id=cid,
                details={
                    "violations": detected_violations,
                    "pii_scrubbed": scrubbed_query != raw_query,
                },
            )
        )

    return {
        "user_query": scrubbed_query,
        "security_violations": detected_violations,
        "tainted_context": is_tainted,
        "loop_count": state.get("loop_count", 0),
        "total_tokens": state.get("total_tokens", 0),
        "accumulated_cost_usd": state.get("accumulated_cost_usd", 0.0),
        "circuit_breaker_tripped": False,
        "active_route": "semantic_cache_memory_node",
    }
