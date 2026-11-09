"""Dual-Channel WebSocket & SSE backpressure multiplexer for real-time visualization."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import Any

from fastapi import WebSocket

from src.modules.orchestration.domain.interfaces import (
    IDualChannelStreamer,
    TokenStreamEvent,
    TopologyEvent,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class DualChannelStreamer(IDualChannelStreamer):
    """Multiplexes topology canvas events (immediate) and synthesis token deltas (50ms throttled)."""

    def __init__(self, throttle_interval_ms: float = 50.0) -> None:
        self.throttle_interval = throttle_interval_ms / 1000.0
        self._active_websockets: set[WebSocket] = set()
        self._sse_queues: set[asyncio.Queue[str]] = set()

        # Token delta accumulator ring buffer
        self._token_buffer: list[str] = []
        self._last_flush_time = 0.0
        self._flush_lock = asyncio.Lock()
        self._accumulated_chars = 0

    def register_websocket(self, ws: WebSocket) -> None:
        """Register client WebSocket for live broadcast."""
        self._active_websockets.add(ws)

    def unregister_websocket(self, ws: WebSocket) -> None:
        """Remove disconnected WebSocket."""
        self._active_websockets.discard(ws)

    def create_sse_queue(self) -> asyncio.Queue[str]:
        """Create and register a subscriber queue for SSE streaming."""
        q: asyncio.Queue[str] = asyncio.Queue()
        self._sse_queues.add(q)
        return q

    def remove_sse_queue(self, q: asyncio.Queue[str]) -> None:
        """Unregister an SSE subscriber queue."""
        self._sse_queues.discard(q)

    async def _broadcast_payload(self, channel: str, data: dict[str, Any]) -> None:
        """Send JSON payload across all active WebSockets and SSE queues."""
        envelope = {"channel": channel, **data}
        raw_msg = json.dumps(envelope, default=str)

        # 1. WebSocket dispatch
        disconnected: list[WebSocket] = []
        for ws in self._active_websockets:
            try:
                await ws.send_text(raw_msg)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self._active_websockets.discard(ws)

        # 2. SSE queue dispatch
        sse_formatted = f"event: {channel}\ndata: {raw_msg}\n\n"
        for q in list(self._sse_queues):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(sse_formatted)

    async def emit_topology(self, event: TopologyEvent) -> None:
        """Channel 1: Immediate 0ms dispatch to React Flow SVG canvas store."""
        await self._broadcast_payload("topology_event", event.model_dump())

    async def emit_token(self, delta: str, correlation_id: str, is_complete: bool = False) -> None:
        """Channel 2: Accumulate token deltas and flush at 50ms intervals."""
        async with self._flush_lock:
            self._token_buffer.append(delta)
            self._accumulated_chars += len(delta)
            now = time.time()

            should_flush = is_complete or (now - self._last_flush_time >= self.throttle_interval)
            if should_flush and self._token_buffer:
                buffered_delta = "".join(self._token_buffer)
                self._token_buffer.clear()
                self._last_flush_time = now

                evt = TokenStreamEvent(
                    delta=buffered_delta,
                    accumulated_length=self._accumulated_chars,
                    is_complete=is_complete,
                    correlation_id=correlation_id,
                )
                await self._broadcast_payload("token_stream_event", evt.model_dump())

            if is_complete:
                self._accumulated_chars = 0
