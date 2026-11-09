"""CQRS Query models and handlers for workflow inspection and time-travel history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.modules.orchestration.application.commands import _orchestrator
from src.shared.cqrs import Query


@dataclass(frozen=True)
class GetWorkflowStateQuery(Query):
    """Query to fetch current AgentState for an active thread."""

    thread_id: str = "default_thread"


@dataclass(frozen=True)
class ListCheckpointsQuery(Query):
    """Query to list all historical checkpoints for a thread."""

    thread_id: str = "default_thread"


async def handle_get_workflow_state(query: GetWorkflowStateQuery) -> dict[str, Any]:
    """Retrieve current state snapshot for thread."""
    history = _orchestrator.get_checkpoint_history(query.thread_id)
    if not history:
        return {"thread_id": query.thread_id, "status": "NOT_STARTED", "state": None}
    return {
        "thread_id": query.thread_id,
        "status": "ACTIVE",
        "latest_checkpoint": history[0].get("checkpoint_id"),
        "state": history[0].get("values"),
    }


async def handle_list_checkpoints(query: ListCheckpointsQuery) -> list[dict[str, Any]]:
    """Retrieve list of checkpoints for time travel."""
    return _orchestrator.get_checkpoint_history(query.thread_id)
