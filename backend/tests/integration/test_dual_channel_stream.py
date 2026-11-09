"""Integration tests for Dual-Channel streaming protocol (Topology vs Token stream)."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.modules.orchestration.application.commands import (
    ExecuteWorkflowCommand,
    handle_execute_workflow,
)
from src.modules.orchestration.domain.interfaces import TopologyEvent
from src.modules.orchestration.infrastructure.dual_channel_streamer import DualChannelStreamer


@pytest.mark.asyncio
async def test_dual_channel_streamer_dispatch() -> None:
    streamer = DualChannelStreamer(throttle_interval_ms=30.0)

    # Attach mock websocket
    mock_ws = AsyncMock()
    streamer.register_websocket(mock_ws)

    # Attach SSE queue
    sse_q = streamer.create_sse_queue()

    # 1. Emit Topology Event (Immediate Channel 1)
    topo_evt = TopologyEvent(
        event_type="node_start",
        node_id="supervisor_router_node",
        status="Running",
        correlation_id="corr_test_123",
    )
    await streamer.emit_topology(topo_evt)

    assert mock_ws.send_text.called
    msg_sent = mock_ws.send_text.call_args[0][0]
    assert "topology_event" in msg_sent
    assert "supervisor_router_node" in msg_sent

    # Verify SSE queue received event
    sse_item = await asyncio.wait_for(sse_q.get(), timeout=1.0)
    assert "event: topology_event" in sse_item

    # 2. Emit Token Stream Events (Throttled Channel 2)
    mock_ws.send_text.reset_mock()
    for word in ["This", "is", "a", "streamed", "response."]:
        await streamer.emit_token(f"{word} ", correlation_id="corr_test_123", is_complete=False)

    # Signal completion
    await streamer.emit_token("", correlation_id="corr_test_123", is_complete=True)

    # Verify token_stream_event was dispatched
    assert mock_ws.send_text.called
    stream_sent = [args[0][0] for args in mock_ws.send_text.call_args_list]
    assert any("token_stream_event" in m for m in stream_sent)


@pytest.mark.asyncio
async def test_workflow_execution_emits_dual_channel_events() -> None:
    streamer = DualChannelStreamer(throttle_interval_ms=20.0)
    sse_queue = streamer.create_sse_queue()

    cmd = ExecuteWorkflowCommand(
        user_query="Summary of Medallion Lakehouse Architecture",
        thread_id="thread_dual_channel",
        streamer=streamer,
    )

    await handle_execute_workflow(cmd)

    # Collect events from SSE queue
    events: list[str] = []
    while not sse_queue.empty():
        events.append(sse_queue.get_nowait())

    assert len(events) > 0
    # Must have both topology events and token stream events
    has_topology = any("topology_event" in e for e in events)
    has_tokens = any("token_stream_event" in e for e in events)

    assert has_topology is True
    assert has_tokens is True
