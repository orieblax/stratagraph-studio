"""Domain interfaces and event payloads for Orchestration and Dual-Channel streaming."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from src.modules.orchestration.domain.state import AgentState


class TopologyEvent(BaseModel):
    """Channel 1 event: immediate 0ms dispatch to React Flow canvas store."""

    event_type: str = Field(
        ...,
        description="node_start, node_end, edge_active, mcp_call, hitl_interrupt, warehouse_warmup, eval_score",
    )
    node_id: str
    status: str = Field(
        default="Running",
        description="Idle, Running, Cache Hit, Warming Warehouse, Tainted, Blocked, Success, Error",
    )
    execution_time_ms: float = 0.0
    token_count: int = 0
    micro_cost_usd: float = 0.0
    tainted: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TokenStreamEvent(BaseModel):
    """Channel 2 event: 50ms throttled delta buffer routed solely to Output Drawer."""

    event_type: str = "token_delta"
    delta: str
    accumulated_length: int = 0
    is_complete: bool = False
    correlation_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


@dataclass
class WorkflowExecutionConfig:
    """Runtime execution configuration injected via RunnableConfig."""

    thread_id: str
    checkpoint_id: str | None = None
    provider: str = "openai"
    model: str = "gpt-4o"
    temperature: float = 0.7
    vector_backend: str = "postgres_local"
    semantic_cache_enabled: bool = True
    semantic_cache_threshold: float = 0.92
    max_iterations: int = 3
    max_cost_usd: float = 1.50
    reranker_device_policy: str = "onnx-int8"
    eval_sampling_rate: float = 0.25
    manual_hitl_tools: list[str] = field(
        default_factory=lambda: ["send_email", "execute_local_write_query", "create_task"]
    )


class IDualChannelStreamer(Protocol):
    """Protocol for broadcasting Dual-Channel WebSocket and SSE events."""

    async def emit_topology(self, event: TopologyEvent) -> None:
        """Immediately emit topology event to React Flow canvas."""
        ...

    async def emit_token(self, delta: str, correlation_id: str, is_complete: bool = False) -> None:
        """Buffer and emit throttled token delta to output drawer."""
        ...


class IWorkflowOrchestrator(Protocol):
    """Protocol for running and checkpointing the LangGraph StateGraph."""

    async def run_workflow(
        self,
        user_query: str,
        config: WorkflowExecutionConfig,
        initial_state: dict[str, Any] | None = None,
    ) -> AgentState:
        """Run workflow from start or checkpoint."""
        ...

    async def resume_workflow(
        self,
        thread_id: str,
        approved: bool,
        modification: dict[str, Any] | None = None,
    ) -> AgentState:
        """Resume execution following an HITL interrupt gate."""
        ...
