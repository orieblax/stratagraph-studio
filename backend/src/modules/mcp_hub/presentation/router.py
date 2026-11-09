"""FastAPI router for Zero-Trust MCP Tool execution, discovery, and audit trail."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.modules.mcp_hub.domain.interfaces import MCPToolCallRequest, MCPToolCallResult
from src.modules.mcp_hub.infrastructure.mcp_client_manager import MCPClientManager
from src.modules.security_guardrails.presentation.middleware import (
    authenticate_request,
    extract_ephemeral_secrets_dependency,
)

router = APIRouter(prefix="/mcp", tags=["MCP Hub"])
_manager = MCPClientManager(use_subprocesses=False)


@router.get("/tools")
async def list_tools_endpoint(
    server_name: str | None = None,
    _user: dict[str, Any] = Depends(authenticate_request),
) -> list[dict[str, Any]]:
    """List available MCP tools across registered servers."""
    tools = _manager.list_tools(server_name)
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters_schema": t.parameters_schema,
            "server_name": t.server_name,
            "is_mutation": t.is_mutation,
            "requires_hitl": t.requires_hitl,
        }
        for t in tools
    ]


@router.post("/call", dependencies=[Depends(extract_ephemeral_secrets_dependency)])
async def execute_tool_endpoint(
    req: MCPToolCallRequest,
    _user: dict[str, Any] = Depends(authenticate_request),
) -> MCPToolCallResult:
    """Execute a sandboxed MCP tool call with AST validation and spotlighting."""
    try:
        return await _manager.execute_tool(req)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP Tool execution failed: {exc}",
        ) from exc


@router.get("/audit")
async def get_audit_trail_endpoint(
    _user: dict[str, Any] = Depends(authenticate_request),
) -> list[dict[str, Any]]:
    """Retrieve audit trail of recent MCP tool calls."""
    return [
        {
            "timestamp": a.timestamp.isoformat(),
            "server_name": a.server_name,
            "tool_name": a.tool_name,
            "arguments": a.arguments,
            "success": a.success,
            "tainted": a.tainted,
            "sql_ast_validated": a.sql_ast_validated,
            "execution_time_ms": a.execution_time_ms,
            "error": a.error,
        }
        for a in _manager.audit_log[-50:]
    ]
