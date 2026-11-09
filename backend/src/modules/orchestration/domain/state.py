"""AgentState TypedDict for LangGraph cyclic workflow execution."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Unified state dictionary passed across all 9 LangGraph nodes."""

    # Workflow & Tracing Context
    messages: list[dict[str, Any]]
    correlation_id: str
    langsmith_run_id: str
    active_route: str  # "etl_ingest", "rag_retrieve", "mcp_tool", "synthesize", "fallback", "end"
    user_query: str
    config_hash: str
    selected_vector_backend: str  # "postgres_local", "supabase_cloud", "databricks_unity_catalog"

    # Security & Taint Tracking
    tainted_context: bool
    spotlight_nonces: list[str]
    hitl_pending_action: dict[str, Any] | None
    hitl_approved: bool | None
    security_violations: list[str]

    # FinOps, Loop Counting & Circuit Breakers
    loop_count: int
    total_tokens: int
    accumulated_cost_usd: float
    circuit_breaker_tripped: bool
    circuit_breaker_reason: str | None

    # Two-Tier Semantic Cache
    cache_hit: bool
    cache_tier: str | None  # "exact", "semantic", None
    cached_response: str | None

    # RAG & Re-Ranking Candidates
    retrieved_chunks: list[dict[str, Any]]
    reranked_chunks: list[dict[str, Any]]
    document_id: str | None

    # Tool Execution & AST Audit
    mcp_scratchpad: list[dict[str, Any]]
    sql_audit_log: list[dict[str, Any]]

    # Databricks Lakehouse & Medallion State
    medallion_status: dict[str, Any]

    # Evals & Output Synthesis
    synthesized_output: str
    structured_synthesis: dict[str, Any] | None
    routing_decision: dict[str, Any] | None
    eval_scores: dict[str, float]
