"""Node 7: MCP Tool Execution Node (Zero-Trust MCP calls, AST checks, HITL gates)."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.modules.mcp_hub.domain.interfaces import MCPToolCallRequest
from src.modules.mcp_hub.infrastructure.mcp_client_manager import MCPClientManager
from src.modules.orchestration.domain.interfaces import TopologyEvent
from src.modules.orchestration.domain.state import AgentState
from src.shared.registry import register_node

NODE_NAME = "mcp_tool_execution_node"
_mcp_manager = MCPClientManager(use_subprocesses=False)


@register_node(NODE_NAME)
async def mcp_tool_execution_node(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    """Execute sandboxed MCP tools with mandatory HITL approval for tainted contexts or mutations."""
    start_time = time.time()
    streamer = config.get("configurable", {}).get("streamer") if config else None
    cid = state.get("correlation_id", "")

    # Parse requested tool from user query or state
    query = state.get("user_query", "").lower()

    # Determine tool target
    if "send email" in query:
        s_name, t_name = "workspace-ops-mcp", "send_email"
        args = {
            "recipient": "ops-lead@enterprise.org",
            "subject": "Automated Notification",
            "body": state.get("user_query", ""),
        }
    elif "create task" in query:
        s_name, t_name = "supabase-cloud-mcp", "create_task"
        args = {
            "title": "Automated System Task",
            "priority": "high",
            "description": state.get("user_query", ""),
        }
    elif "query lakehouse" in query:
        s_name, t_name = "databricks-lakehouse-mcp", "query_lakehouse_sql"
        args = {"query": "SELECT * FROM bronze_documents LIMIT 5"}
    elif "sql write" in query or "insert into" in query:
        s_name, t_name = "postgres-local-mcp", "execute_local_write_query"
        args = {
            "query": "INSERT INTO etl_outbox (document_id, file_name, file_path) VALUES ('doc_test', 'test.txt', '/safe/test.txt')"
        }
    else:
        s_name, t_name = "postgres-local-mcp", "inspect_local_schema"
        args = {}

    manual_hitl_tools = (
        config.get("configurable", {}).get("manual_hitl_tools") if config else None
    ) or ["send_email", "execute_local_write_query", "create_task"]

    is_tainted = state.get("tainted_context", False)
    is_mutation = t_name in manual_hitl_tools
    hitl_decision = state.get("hitl_approved")

    # 1. Trigger Human-In-The-Loop gate if context is tainted or action is mutating and not yet decided
    if (is_tainted or is_mutation) and hitl_decision is None:
        exec_ms = round((time.time() - start_time) * 1000, 2)
        pending_action = {
            "server_name": s_name,
            "tool_name": t_name,
            "arguments": args,
            "reason": "Tainted context from external documents"
            if is_tainted
            else "Side-effect mutating tool execution",
        }
        if streamer:
            await streamer.emit_topology(
                TopologyEvent(
                    event_type="hitl_interrupt",
                    node_id=NODE_NAME,
                    status="Tainted / HITL Locked",
                    execution_time_ms=exec_ms,
                    tainted=is_tainted,
                    correlation_id=cid,
                    details=pending_action,
                )
            )
        return {
            "hitl_pending_action": pending_action,
            "active_route": "mcp_tool_execution_node",
        }

    # 2. Check for human rejection
    if hitl_decision is False:
        exec_ms = round((time.time() - start_time) * 1000, 2)
        scratchpad = list(state.get("mcp_scratchpad") or [])
        scratchpad.append(
            {
                "tool": t_name,
                "server": s_name,
                "status": "REJECTED_BY_OPERATOR",
                "message": "Human operator rejected execution of tool.",
            }
        )
        if streamer:
            await streamer.emit_topology(
                TopologyEvent(
                    event_type="node_end",
                    node_id=NODE_NAME,
                    status="Blocked by Guardrail",
                    execution_time_ms=exec_ms,
                    correlation_id=cid,
                    details={"status": "REJECTED_BY_OPERATOR"},
                )
            )
        return {
            "mcp_scratchpad": scratchpad,
            "hitl_pending_action": None,
            "hitl_approved": None,
            "active_route": "supervisor_router_node",
        }

    # 3. Execute authorized tool call
    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_start",
                node_id=NODE_NAME,
                status="Running",
                correlation_id=cid,
                details={"server": s_name, "tool": t_name},
            )
        )

    req = MCPToolCallRequest(
        server_name=s_name,
        tool_name=t_name,
        arguments=args,
        correlation_id=cid,
    )
    result = await _mcp_manager.execute_tool(req)
    exec_ms = round((time.time() - start_time) * 1000, 2)

    scratchpad = list(state.get("mcp_scratchpad") or [])
    scratchpad.append(
        {
            "server": s_name,
            "tool": t_name,
            "success": result.success,
            "output": result.output,
            "error": result.error_message,
            "execution_time_ms": result.execution_time_ms,
        }
    )

    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_end",
                node_id=NODE_NAME,
                status="Success" if result.success else "Error",
                execution_time_ms=exec_ms,
                tainted=result.tainted,
                correlation_id=cid,
                details={"tool": t_name, "success": result.success},
            )
        )

    return {
        "mcp_scratchpad": scratchpad,
        "hitl_pending_action": None,
        "hitl_approved": None,
        "active_route": "supervisor_router_node",
    }
