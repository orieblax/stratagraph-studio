"""Zero-Trust MCP Client Manager orchestrating isolated stdio and remote SSE MCP servers."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.modules.mcp_hub.domain.interfaces import (
    IMCPToolExecutor,
    MCPAuditEntry,
    MCPToolCallRequest,
    MCPToolCallResult,
    MCPToolDefinition,
)
from src.modules.mcp_hub.infrastructure.servers import (
    databricks_lakehouse_mcp,
    postgres_local_mcp,
    supabase_cloud_mcp,
    workspace_ops_mcp,
)
from src.modules.security_guardrails.infrastructure.spotlighting import SpotlightingEngine
from src.modules.security_guardrails.infrastructure.sql_validator import SQLSecurityValidator
from src.shared.ephemeral_secrets import EphemeralSecretVault
from src.shared.logging import get_logger

logger = get_logger(__name__)

# Basic environment variable allowlist for stdio subprocess isolation
_ALLOWED_ENV_VARS = {
    "SYSTEMROOT",
    "PATH",
    "PYTHONPATH",
    "TEMP",
    "TMP",
    "SAFE_UPLOAD_DIR",
    "ENVIRONMENT",
}


class MCPClientManager(IMCPToolExecutor):
    """Orchestrates secure stdio and remote SSE MCP tool executions with AST validation and spotlighting."""

    def __init__(self, use_subprocesses: bool = False) -> None:
        self.use_subprocesses = use_subprocesses
        self.spotlighter = SpotlightingEngine()
        self.sql_validator = SQLSecurityValidator()
        self.audit_log: list[MCPAuditEntry] = []

        # Internal registry mapping server name to its tools and in-memory handler
        self._servers: dict[str, dict[str, Any]] = {
            postgres_local_mcp.SERVER_NAME: {
                "tools": postgres_local_mcp.TOOLS,
                "handler": postgres_local_mcp.handle_call,
                "module": "src.modules.mcp_hub.infrastructure.servers.postgres_local_mcp",
                "secret_keys": ["DATABASE_URL"],
            },
            supabase_cloud_mcp.SERVER_NAME: {
                "tools": supabase_cloud_mcp.TOOLS,
                "handler": supabase_cloud_mcp.handle_call,
                "module": "src.modules.mcp_hub.infrastructure.servers.supabase_cloud_mcp",
                "secret_keys": ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"],
            },
            databricks_lakehouse_mcp.SERVER_NAME: {
                "tools": databricks_lakehouse_mcp.TOOLS,
                "handler": databricks_lakehouse_mcp.handle_call,
                "module": "src.modules.mcp_hub.infrastructure.servers.databricks_lakehouse_mcp",
                "secret_keys": [
                    "DATABRICKS_HOST",
                    "DATABRICKS_TOKEN",
                    "DATABRICKS_SQL_WAREHOUSE_ID",
                ],
            },
            workspace_ops_mcp.SERVER_NAME: {
                "tools": workspace_ops_mcp.TOOLS,
                "handler": workspace_ops_mcp.handle_call,
                "module": "src.modules.mcp_hub.infrastructure.servers.workspace_ops_mcp",
                "secret_keys": ["SAFE_UPLOAD_DIR"],
            },
        }

        # Remote SSE/HTTP MCP server endpoints
        self._remote_servers: dict[str, dict[str, str]] = {}

    def register_remote_mcp_server(
        self, name: str, sse_url: str, bearer_token: str | None = None
    ) -> None:
        """Register a remote SSE/HTTP MCP server endpoint."""
        self._remote_servers[name] = {
            "url": sse_url,
            "token": bearer_token or "",
        }

    def list_tools(self, server_name: str | None = None) -> list[MCPToolDefinition]:
        """Discover available tools across registered servers."""
        tools: list[MCPToolDefinition] = []
        for s_name, s_data in self._servers.items():
            if server_name and s_name != server_name:
                continue
            tools.extend(s_data["tools"])
        return tools

    def _build_scrubbed_env(self, server_name: str) -> dict[str, str]:
        """Construct a minimal, hardened environment dictionary for subprocess isolation."""
        scrubbed: dict[str, str] = {}
        for var in _ALLOWED_ENV_VARS:
            val = os.getenv(var)
            if val is not None:
                scrubbed[var] = val

        # Explicitly inject only secrets approved for this specific server
        server_info = self._servers.get(server_name, {})
        allowed_secrets = server_info.get("secret_keys", [])
        for secret_key in allowed_secrets:
            val = EphemeralSecretVault.get_secret_value(secret_key, os.getenv(secret_key))
            if val is not None:
                scrubbed[secret_key] = val

        return scrubbed

    async def _execute_via_subprocess(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """Execute JSON-RPC call against an isolated stdio Python subprocess."""
        server_info = self._servers[server_name]
        module_path = server_info["module"]
        scrubbed_env = self._build_scrubbed_env(server_name)

        cmd = [sys.executable, "-m", module_path]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=scrubbed_env,
        )

        req_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        input_data = (json.dumps(req_payload) + "\n").encode("utf-8")

        stdout, stderr = await proc.communicate(input_data)
        if proc.returncode != 0:
            err_msg = (
                stderr.decode("utf-8").strip() or f"Process exited with code {proc.returncode}"
            )
            raise RuntimeError(f"MCP Subprocess execution failed: {err_msg}")

        out_lines = stdout.decode("utf-8").strip().splitlines()
        for line in out_lines:
            try:
                rpc_resp = json.loads(line)
                if "error" in rpc_resp:
                    raise RuntimeError(rpc_resp["error"].get("message", "MCP Tool Error"))
                if "result" in rpc_resp and "content" in rpc_resp["result"]:
                    content = rpc_resp["result"]["content"]
                    if content and isinstance(content, list):
                        return json.loads(content[0]["text"])
                return rpc_resp.get("result")
            except json.JSONDecodeError:
                continue

        raise RuntimeError("No valid JSON-RPC response received from MCP subprocess.")

    async def _execute_remote_sse_mcp(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """Execute tool on a remote SSE/HTTP MCP server."""
        info = self._remote_servers[server_name]
        url = info["url"]
        headers = {"Content-Type": "application/json"}
        if info["token"]:
            headers["Authorization"] = f"Bearer {info['token']}"

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(data["error"].get("message", "Remote MCP Error"))
            return data.get("result")

    async def execute_tool(self, request: MCPToolCallRequest) -> MCPToolCallResult:
        """Validate, intercept, execute, and spotlight an MCP tool request."""
        start_time = time.time()
        s_name = request.server_name
        t_name = request.tool_name
        args = request.arguments

        # 1. Server validation
        is_remote = s_name in self._remote_servers
        if s_name not in self._servers and not is_remote:
            return MCPToolCallResult(
                success=False,
                server_name=s_name,
                tool_name=t_name,
                output=None,
                error_message=f"MCP Server '{s_name}' is not registered.",
            )

        # 2. SQL AST Pre-Execution Security Gate
        sql_arg = args.get("query") or args.get("sql")
        is_sql_validated = False
        if isinstance(sql_arg, str):
            read_only_mode = "write" not in t_name.lower()
            val_result = self.sql_validator.validate_and_rewrite(
                sql_arg,
                dialect="postgres" if "postgres" in s_name else "databricks",
                read_only=read_only_mode,
            )
            # Replace raw query with AST-sanitized query
            args = dict(args)
            if "query" in args:
                args["query"] = val_result.sanitized_sql
            elif "sql" in args:
                args["sql"] = val_result.sanitized_sql
            is_sql_validated = True

        # 3. Execution with tenacity retries
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=4),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    if is_remote:
                        raw_output = await self._execute_remote_sse_mcp(s_name, t_name, args)
                    elif self.use_subprocesses:
                        raw_output = await self._execute_via_subprocess(s_name, t_name, args)
                    else:
                        handler = self._servers[s_name]["handler"]
                        raw_output = await handler(t_name, args)

            exec_ms = round((time.time() - start_time) * 1000, 2)

            # 4. Spotlighting & Taint Wrapping of tool outputs
            raw_text = json.dumps(raw_output) if not isinstance(raw_output, str) else raw_output
            spotlight_res = self.spotlighter.wrap_untrusted_content(
                raw_text, source_id=f"mcp://{s_name}/{t_name}"
            )

            # Record Audit Log
            self.audit_log.append(
                MCPAuditEntry(
                    server_name=s_name,
                    tool_name=t_name,
                    arguments={
                        k: ("********" if "token" in k or "key" in k else v)
                        for k, v in args.items()
                    },
                    success=True,
                    tainted=spotlight_res.tainted,
                    sql_ast_validated=is_sql_validated,
                    execution_time_ms=exec_ms,
                )
            )

            return MCPToolCallResult(
                success=True,
                server_name=s_name,
                tool_name=t_name,
                output=spotlight_res.spotlighted_text,
                execution_time_ms=exec_ms,
                tainted=spotlight_res.tainted,
                metadata={
                    "nonce": spotlight_res.nonce,
                    "correlation_id": request.correlation_id,
                    "langsmith_run_id": request.langsmith_run_id,
                },
            )

        except Exception as exc:
            exec_ms = round((time.time() - start_time) * 1000, 2)
            self.audit_log.append(
                MCPAuditEntry(
                    server_name=s_name,
                    tool_name=t_name,
                    arguments=args,
                    success=False,
                    tainted=False,
                    sql_ast_validated=is_sql_validated,
                    execution_time_ms=exec_ms,
                    error=str(exc),
                )
            )
            return MCPToolCallResult(
                success=False,
                server_name=s_name,
                tool_name=t_name,
                output=None,
                error_message=str(exc),
                execution_time_ms=exec_ms,
                tainted=False,
            )
