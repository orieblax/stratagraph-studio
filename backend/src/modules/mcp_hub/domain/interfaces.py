"""Domain models, protocols, and audit records for Zero-Trust MCP Hub."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class MCPToolCallRequest(BaseModel):
    """Zero-trust validated tool call request payload."""

    model_config = ConfigDict(extra="forbid", str_max_length=10000)

    server_name: str = Field(..., description="Target MCP server identifier")
    tool_name: str = Field(..., description="Specific tool operation to execute")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Validated arguments dictionary"
    )
    correlation_id: str = Field(default="", description="Request correlation tracking ID")
    langsmith_run_id: str = Field(default="", description="LangSmith parent run ID")


class MCPToolCallResult(BaseModel):
    """Result of an MCP tool invocation."""

    success: bool
    server_name: str
    tool_name: str
    output: Any
    error_message: str | None = None
    execution_time_ms: float = 0.0
    tainted: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class MCPToolDefinition:
    """Schema metadata describing an available MCP tool."""

    name: str
    description: str
    parameters_schema: dict[str, Any]
    server_name: str
    is_mutation: bool = False
    requires_hitl: bool = False


@dataclass(frozen=True)
class MCPAuditEntry:
    """Audit log entry capturing MCP tool execution parameters and security status."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    server_name: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    tainted: bool = False
    sql_ast_validated: bool = False
    hitl_approved: bool = False
    execution_time_ms: float = 0.0
    error: str | None = None


class IMCPToolExecutor(Protocol):
    """Protocol for executing MCP tools across stdio and remote transports."""

    async def execute_tool(self, request: MCPToolCallRequest) -> MCPToolCallResult:
        """Execute a validated tool call against an MCP server."""
        ...

    def list_tools(self, server_name: str | None = None) -> list[MCPToolDefinition]:
        """List all discovered MCP tools."""
        ...
