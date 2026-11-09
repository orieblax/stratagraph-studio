"""FastAPI router for Workflow Orchestration, Time-Travel Checkpointing, and Dual-Channel Streaming."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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
from src.modules.orchestration.infrastructure.dual_channel_streamer import DualChannelStreamer
from src.modules.security_guardrails.presentation.middleware import (
    authenticate_request,
    extract_ephemeral_secrets_dependency,
)

router = APIRouter(prefix="/orchestration", tags=["Orchestration"])
streamer = DualChannelStreamer(throttle_interval_ms=50.0)


class RunWorkflowRequest(BaseModel):
    user_query: str = Field(..., description="User prompt or workflow instructions")
    thread_id: str = Field(default="default_thread")
    provider: str = Field(default="openai")
    model: str = Field(default="gpt-4o")
    temperature: float = Field(default=0.7)
    vector_backend: str = Field(default="postgres_local")
    semantic_cache_enabled: bool = Field(default=True)
    semantic_cache_threshold: float = Field(default=0.92)
    max_iterations: int = Field(default=3)
    max_cost_usd: float = Field(default=1.50)
    reranker_device_policy: str = Field(default="onnx-int8")
    eval_sampling_rate: float = Field(default=0.25)
    manual_hitl_tools: list[str] = Field(
        default_factory=lambda: ["send_email", "execute_local_write_query", "create_task"]
    )


class ResumeWorkflowRequest(BaseModel):
    thread_id: str = Field(default="default_thread")
    approved: bool = Field(default=True)
    modification: dict[str, Any] | None = None


class ForkCheckpointRequest(BaseModel):
    thread_id: str = Field(default="default_thread")
    checkpoint_id: str
    new_thread_id: str
    modified_state: dict[str, Any] | None = None


@router.post("/run", dependencies=[Depends(extract_ephemeral_secrets_dependency)])
async def run_workflow_endpoint(
    req: RunWorkflowRequest,
    _user: dict[str, Any] = Depends(authenticate_request),
) -> dict[str, Any]:
    """Execute multi-agent workflow through LangGraph."""
    cmd = ExecuteWorkflowCommand(
        user_query=req.user_query,
        thread_id=req.thread_id,
        provider=req.provider,
        model=req.model,
        temperature=req.temperature,
        vector_backend=req.vector_backend,
        semantic_cache_enabled=req.semantic_cache_enabled,
        semantic_cache_threshold=req.semantic_cache_threshold,
        max_iterations=req.max_iterations,
        max_cost_usd=req.max_cost_usd,
        reranker_device_policy=req.reranker_device_policy,
        eval_sampling_rate=req.eval_sampling_rate,
        manual_hitl_tools=req.manual_hitl_tools,
        streamer=streamer,
    )
    result_state = await handle_execute_workflow(cmd)
    return {
        "status": "COMPLETED" if not result_state.get("hitl_pending_action") else "HITL_INTERRUPT",
        "thread_id": req.thread_id,
        "state": result_state,
    }


@router.post("/resume", dependencies=[Depends(extract_ephemeral_secrets_dependency)])
async def resume_workflow_endpoint(
    req: ResumeWorkflowRequest,
    _user: dict[str, Any] = Depends(authenticate_request),
) -> dict[str, Any]:
    """Resume execution following an HITL interrupt."""
    cmd = ResumeWorkflowCommand(
        thread_id=req.thread_id,
        approved=req.approved,
        modification=req.modification,
        streamer=streamer,
    )
    result_state = await handle_resume_workflow(cmd)
    return {
        "status": "RESUMED",
        "thread_id": req.thread_id,
        "state": result_state,
    }


@router.post("/fork", dependencies=[Depends(extract_ephemeral_secrets_dependency)])
async def fork_checkpoint_endpoint(
    req: ForkCheckpointRequest,
    _user: dict[str, Any] = Depends(authenticate_request),
) -> dict[str, Any]:
    """Time-travel / fork workflow from historical checkpoint."""
    cmd = ForkCheckpointCommand(
        thread_id=req.thread_id,
        checkpoint_id=req.checkpoint_id,
        new_thread_id=req.new_thread_id,
        modified_state=req.modified_state,
    )
    return await handle_fork_checkpoint(cmd)


@router.get("/checkpoints/{thread_id}")
async def list_checkpoints_endpoint(
    thread_id: str,
    _user: dict[str, Any] = Depends(authenticate_request),
) -> list[dict[str, Any]]:
    """Retrieve historical checkpoints for thread inspection."""
    return await handle_list_checkpoints(ListCheckpointsQuery(thread_id=thread_id))


@router.get("/stream")
async def sse_stream_endpoint() -> StreamingResponse:
    """Channel 1 & Channel 2 Server-Sent Events (SSE) stream."""
    queue = streamer.create_sse_queue()

    async def event_generator() -> Any:
        try:
            while True:
                data = await queue.get()
                yield data
        except asyncio.CancelledError:
            streamer.remove_sse_queue(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Dual-Channel WebSocket endpoint for 60fps canvas topology and throttled token streams."""
    await websocket.accept()
    streamer.register_websocket(websocket)
    try:
        while True:
            # Keep connection alive and receive client commands
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        streamer.unregister_websocket(websocket)
