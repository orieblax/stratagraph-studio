"""Integration tests for Human-in-the-Loop approval gates and Time-Travel checkpoint forking."""

import pytest

from src.modules.orchestration.application.commands import (
    ExecuteWorkflowCommand,
    ForkCheckpointCommand,
    ResumeWorkflowCommand,
    handle_execute_workflow,
    handle_fork_checkpoint,
    handle_resume_workflow,
)
from src.modules.orchestration.application.queries import (
    ListCheckpointsQuery,
    handle_list_checkpoints,
)


@pytest.mark.asyncio
async def test_hitl_interrupt_and_operator_approval() -> None:
    thread_id = "thread_hitl_gate_test"

    # 1. Trigger action that requires mandatory Human-in-the-Loop gate (send_email)
    cmd = ExecuteWorkflowCommand(
        user_query="Please send email to ops-lead regarding status",
        thread_id=thread_id,
        manual_hitl_tools=["send_email"],
    )

    state_before_approval = await handle_execute_workflow(cmd)

    # Verify execution paused at HITL gate with pending action metadata
    assert state_before_approval.get("hitl_pending_action") is not None
    pending = state_before_approval["hitl_pending_action"]
    assert pending["tool_name"] == "send_email"

    # 2. Operator reviews pending action and approves
    resume_cmd = ResumeWorkflowCommand(
        thread_id=thread_id,
        approved=True,
    )
    state_after_approval = await handle_resume_workflow(resume_cmd)

    # Verify execution completed tool invocation
    assert state_after_approval.get("hitl_pending_action") is None
    mcp_out = state_after_approval.get("mcp_scratchpad")
    assert mcp_out is not None and len(mcp_out) > 0
    assert mcp_out[0]["tool"] == "send_email"
    assert mcp_out[0]["success"] is True


@pytest.mark.asyncio
async def test_time_travel_checkpoint_history_and_forking() -> None:
    thread_id = "thread_timetravel_test"

    cmd = ExecuteWorkflowCommand(
        user_query="Initial query for checkpointing",
        thread_id=thread_id,
    )
    await handle_execute_workflow(cmd)

    # 1. Inspect checkpoint history
    history = await handle_list_checkpoints(ListCheckpointsQuery(thread_id=thread_id))
    assert len(history) > 0

    target_checkpoint = history[0]["checkpoint_id"]

    # 2. Fork state to a new thread (Time Travel)
    fork_cmd = ForkCheckpointCommand(
        thread_id=thread_id,
        checkpoint_id=target_checkpoint,
        new_thread_id="thread_timetravel_forked",
        modified_state={"user_query": "Modified query in forked timeline"},
    )
    fork_res = await handle_fork_checkpoint(fork_cmd)

    assert fork_res["status"] == "FORKED"
    assert fork_res["new_thread_id"] == "thread_timetravel_forked"
    assert fork_res["forked_state"]["user_query"] == "Modified query in forked timeline"
