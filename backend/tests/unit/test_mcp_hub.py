"""Unit tests for Zero-Trust MCPClientManager, isolated servers, and security interceptors."""

import pytest
from pydantic import ValidationError

from src.modules.mcp_hub.domain.interfaces import MCPToolCallRequest
from src.modules.mcp_hub.infrastructure.mcp_client_manager import MCPClientManager
from src.modules.security_guardrails.domain.exceptions import SQLSecurityViolationError


@pytest.fixture
def mcp_manager() -> MCPClientManager:
    return MCPClientManager(use_subprocesses=False)


def test_list_tools_discovers_all_server_tools(mcp_manager: MCPClientManager) -> None:
    tools = mcp_manager.list_tools()
    tool_names = [t.name for t in tools]

    assert "inspect_local_schema" in tool_names
    assert "execute_local_read_query" in tool_names
    assert "create_task" in tool_names
    assert "list_tasks" in tool_names
    assert "list_unity_catalog_tables" in tool_names
    assert "inspect_medallion_lineage" in tool_names
    assert "send_email" in tool_names
    assert "trigger_webhook" in tool_names
    assert "list_safe_uploads" in tool_names


def test_mcp_request_schema_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        MCPToolCallRequest(
            server_name="postgres-local-mcp",
            tool_name="inspect_local_schema",
            arguments={},
            extra_malicious_field="injection",  # type: ignore[call-arg]
        )


def test_scrubbed_env_allows_only_strict_keys(mcp_manager: MCPClientManager) -> None:
    env = mcp_manager._build_scrubbed_env("postgres-local-mcp")
    assert "PATH" in env or "SYSTEMROOT" in env
    # Verify random host environment keys are NOT leaked into the subprocess
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "GITHUB_TOKEN" not in env


@pytest.mark.asyncio
async def test_mcp_blocks_forbidden_sql_in_tool_call(mcp_manager: MCPClientManager) -> None:
    req = MCPToolCallRequest(
        server_name="postgres-local-mcp",
        tool_name="execute_local_read_query",
        arguments={"query": "DROP TABLE critical_data;"},
    )
    with pytest.raises(SQLSecurityViolationError, match="Forbidden SQL operation detected"):
        await mcp_manager.execute_tool(req)


@pytest.mark.asyncio
async def test_mcp_tool_execution_spotlights_output(mcp_manager: MCPClientManager) -> None:
    req = MCPToolCallRequest(
        server_name="workspace-ops-mcp",
        tool_name="send_email",
        arguments={
            "recipient": "lead.architect@enterprise.io",
            "subject": "System Sync",
            "body": "Workflows running smoothly.",
        },
    )
    result = await mcp_manager.execute_tool(req)

    assert result.success is True
    assert result.tainted is True
    assert "<untrusted_context_" in str(result.output)
    assert "</untrusted_context_" in str(result.output)
    assert len(mcp_manager.audit_log) > 0
    assert mcp_manager.audit_log[-1].tool_name == "send_email"


@pytest.mark.asyncio
async def test_mcp_webhook_blocks_ssrf_attacks(mcp_manager: MCPClientManager) -> None:
    # Attempt SSRF toward loopback
    req = MCPToolCallRequest(
        server_name="workspace-ops-mcp",
        tool_name="trigger_webhook",
        arguments={"url": "http://127.0.0.1:8000/api/internal"},
    )
    result = await mcp_manager.execute_tool(req)

    assert result.success is False
    assert "SSRF Security Violation" in str(result.error_message)


@pytest.mark.asyncio
async def test_supabase_mcp_create_and_list_tasks(mcp_manager: MCPClientManager) -> None:
    req = MCPToolCallRequest(
        server_name="supabase-cloud-mcp",
        tool_name="create_task",
        arguments={"title": "Audit Vector Indexes", "priority": "high"},
    )
    res = await mcp_manager.execute_tool(req)
    assert res.success is True
    assert res.tainted is True


@pytest.mark.asyncio
async def test_databricks_mcp_inspect_medallion(mcp_manager: MCPClientManager) -> None:
    req = MCPToolCallRequest(
        server_name="databricks-lakehouse-mcp",
        tool_name="inspect_medallion_lineage",
        arguments={"document_id": "doc_medallion_456"},
    )
    res = await mcp_manager.execute_tool(req)
    assert res.success is True
    assert "doc_medallion_456" in str(res.output)
