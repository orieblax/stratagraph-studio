"""PostgreSQL Local MCP Server: isolated schema inspection and gated query execution."""

from __future__ import annotations

import json
import sys
from typing import Any

from sqlalchemy import text

from src.modules.mcp_hub.domain.interfaces import MCPToolDefinition
from src.modules.security_guardrails.infrastructure.sql_validator import SQLSecurityValidator
from src.shared.database import async_session_factory

SERVER_NAME = "postgres-local-mcp"
_validator = SQLSecurityValidator()

TOOLS = [
    MCPToolDefinition(
        name="inspect_local_schema",
        description="Inspect public tables, columns, and data types in the local PostgreSQL database.",
        parameters_schema={
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "Optional specific table to inspect",
                }
            },
            "additionalProperties": False,
        },
        server_name=SERVER_NAME,
        is_mutation=False,
        requires_hitl=False,
    ),
    MCPToolDefinition(
        name="execute_local_read_query",
        description="Execute a validated read-only SELECT query against the local PostgreSQL database.",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The read-only SQL query to execute"}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        server_name=SERVER_NAME,
        is_mutation=False,
        requires_hitl=False,
    ),
    MCPToolDefinition(
        name="execute_local_write_query",
        description="Execute an authorized write query (INSERT/UPDATE/DELETE). Requires HITL gate.",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The mutation SQL query to execute"}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        server_name=SERVER_NAME,
        is_mutation=True,
        requires_hitl=True,
    ),
]


async def inspect_local_schema(table_name: str | None = None) -> list[dict[str, Any]]:
    """Return schema information from information_schema."""
    query = """
        SELECT table_name, column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
    """
    params: dict[str, Any] = {}
    if table_name:
        query += " AND table_name = :tname"
        params["tname"] = table_name
    query += " ORDER BY table_name, ordinal_position"

    async with async_session_factory() as session:
        res = await session.execute(text(query), params)
        rows = res.fetchall()
        return [
            {
                "table_name": str(r[0]),
                "column_name": str(r[1]),
                "data_type": str(r[2]),
                "is_nullable": str(r[3]),
            }
            for r in rows
        ]


async def execute_local_read_query(query: str) -> list[dict[str, Any]]:
    """Execute a read-only query with AST validation and clamped limit."""
    val_res = _validator.validate_and_rewrite(query, dialect="postgres", read_only=True)
    async with async_session_factory() as session:
        res = await session.execute(text(val_res.sanitized_sql))
        columns = list(res.keys())
        rows = res.fetchall()
        return [dict(zip(columns, row, strict=False)) for row in rows]


async def execute_local_write_query(query: str) -> dict[str, Any]:
    """Execute an authorized mutation query with AST validation."""
    val_res = _validator.validate_and_rewrite(query, dialect="postgres", read_only=False)
    async with async_session_factory() as session, session.begin():
        res = await session.execute(text(val_res.sanitized_sql))
        count = getattr(res, "rowcount", 0)
        return {
            "status": "SUCCESS",
            "affected_rows": int(count if count is not None else 0),
            "tables_accessed": val_res.tables_accessed,
        }


async def handle_call(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Internal dispatch handler for tool invocations."""
    if tool_name == "inspect_local_schema":
        return await inspect_local_schema(arguments.get("table_name"))
    elif tool_name == "execute_local_read_query":
        return await execute_local_read_query(arguments["query"])
    elif tool_name == "execute_local_write_query":
        return await execute_local_write_query(arguments["query"])
    raise ValueError(f"Unknown tool: {tool_name}")


if __name__ == "__main__":
    # stdio JSON-RPC server mode when spawned as an isolated subprocess
    import asyncio

    async def main() -> None:
        for line in sys.stdin:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                rpc = json.loads(line_str)
                req_id = rpc.get("id")
                method = rpc.get("method")
                params = rpc.get("params", {})

                if method == "tools/list":
                    res = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "tools": [
                                {
                                    "name": t.name,
                                    "description": t.description,
                                    "inputSchema": t.parameters_schema,
                                }
                                for t in TOOLS
                            ]
                        },
                    }
                elif method == "tools/call":
                    tool_name = params.get("name")
                    args = params.get("arguments", {})
                    out = await handle_call(tool_name, args)
                    res = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"content": [{"type": "text", "text": json.dumps(out)}]},
                    }
                else:
                    res = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": "Method not found"},
                    }
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                err_res = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32000, "message": str(exc)},
                }
                sys.stdout.write(json.dumps(err_res) + "\n")
                sys.stdout.flush()

    asyncio.run(main())
