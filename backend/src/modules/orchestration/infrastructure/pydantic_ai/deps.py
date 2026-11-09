"""Typed dependency contexts for Pydantic AI micro-agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RouterDeps:
    """Runtime dependencies injected into the Supervisor Router Agent."""

    user_query: str
    loop_count: int = 1
    accumulated_cost_usd: float = 0.0
    max_iterations: int = 3
    max_cost_usd: float = 1.50
    has_mcp_scratchpad: bool = False
    selected_vector_backend: str = "postgres_local"
    allowed_routes: list[str] = field(
        default_factory=lambda: [
            "etl_medallion_embedding_node",
            "hybrid_retriever_node",
            "mcp_tool_execution_node",
            "synthesis_output_guardrail_node",
        ]
    )


@dataclass
class SynthesisDeps:
    """Runtime dependencies injected into the Synthesis Agent."""

    user_query: str
    context_chunks: list[dict[str, Any]] = field(default_factory=list)
    mcp_scratchpad: list[dict[str, Any]] = field(default_factory=list)
    correlation_id: str = ""
    provider: str = "openai"


@dataclass
class GuardrailDeps:
    """Runtime dependencies injected into the Input Guardrail Agent."""

    raw_query: str
    strict_mode: bool = True
    blocked_keywords: list[str] = field(
        default_factory=lambda: [
            "ignore previous instructions",
            "system override",
            "reveal system prompt",
            "bypass guardrails",
        ]
    )
