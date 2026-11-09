"""CQRS Command models and handlers for workflow orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.modules.orchestration.domain.interfaces import WorkflowExecutionConfig
from src.modules.orchestration.domain.state import AgentState
from src.modules.orchestration.infrastructure.graph_builder import LangGraphWorkflowOrchestrator
from src.shared.cqrs import Command

_orchestrator = LangGraphWorkflowOrchestrator()


@dataclass(frozen=True)
class ExecuteWorkflowCommand(Command):
    """Command to trigger a multi-agent visual workflow run."""

    user_query: str = ""
    thread_id: str = "default_thread"
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
    manual_hitl_tools: list[str] | None = None
    streamer: Any = None


@dataclass(frozen=True)
class ResumeWorkflowCommand(Command):
    """Command to resume execution after Human-in-the-Loop decision."""

    thread_id: str = "default_thread"
    approved: bool = True
    modification: dict[str, Any] | None = None
    streamer: Any = None


@dataclass(frozen=True)
class ForkCheckpointCommand(Command):
    """Command to fork execution from a historical checkpoint (Time Travel)."""

    thread_id: str = "default_thread"
    checkpoint_id: str = ""
    new_thread_id: str = ""
    modified_state: dict[str, Any] | None = None


async def handle_execute_workflow(cmd: ExecuteWorkflowCommand) -> AgentState:
    """Execute new workflow through LangGraph."""
    config = WorkflowExecutionConfig(
        thread_id=cmd.thread_id,
        provider=cmd.provider,
        model=cmd.model,
        temperature=cmd.temperature,
        vector_backend=cmd.vector_backend,
        semantic_cache_enabled=cmd.semantic_cache_enabled,
        semantic_cache_threshold=cmd.semantic_cache_threshold,
        max_iterations=cmd.max_iterations,
        max_cost_usd=cmd.max_cost_usd,
        reranker_device_policy=cmd.reranker_device_policy,
        eval_sampling_rate=cmd.eval_sampling_rate,
        manual_hitl_tools=cmd.manual_hitl_tools
        or ["send_email", "execute_local_write_query", "create_task"],
    )
    return await _orchestrator.run_workflow(
        user_query=cmd.user_query,
        config=config,
        streamer=cmd.streamer,
    )


async def handle_resume_workflow(cmd: ResumeWorkflowCommand) -> AgentState:
    """Resume workflow after HITL decision."""
    return await _orchestrator.resume_workflow(
        thread_id=cmd.thread_id,
        approved=cmd.approved,
        modification=cmd.modification,
        streamer=cmd.streamer,
    )


async def handle_fork_checkpoint(cmd: ForkCheckpointCommand) -> dict[str, Any]:
    """Fork workflow from a historical checkpoint ID."""
    history = _orchestrator.get_checkpoint_history(cmd.thread_id)
    target = next((h for h in history if h.get("checkpoint_id") == cmd.checkpoint_id), None)
    if not target:
        raise KeyError(f"Checkpoint '{cmd.checkpoint_id}' not found in thread '{cmd.thread_id}'.")

    # In a full PostgresSaver deployment, we copy the checkpoint row to the new thread_id
    forked_state = dict(target["values"])
    if cmd.modified_state:
        forked_state.update(cmd.modified_state)

    return {
        "status": "FORKED",
        "original_thread_id": cmd.thread_id,
        "new_thread_id": cmd.new_thread_id,
        "checkpoint_id": cmd.checkpoint_id,
        "forked_state": forked_state,
    }
