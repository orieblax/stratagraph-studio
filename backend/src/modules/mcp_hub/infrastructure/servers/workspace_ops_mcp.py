"""Workspace Ops MCP Server: side-effect operations (email, webhook, safe file listing)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from src.modules.mcp_hub.domain.interfaces import MCPToolDefinition
from src.modules.security_guardrails.infrastructure.file_ssrf_validator import SSRFValidator
from src.modules.security_guardrails.infrastructure.pii_scrubber import _EMAIL_REGEX

SERVER_NAME = "workspace-ops-mcp"
_ssrf_validator = SSRFValidator()

TOOLS = [
    MCPToolDefinition(
        name="send_email",
        description="Dispatch an email notification. Gated by mandatory Human-in-the-Loop approval.",
        parameters_schema={
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Destination email address"},
                "subject": {"type": "string", "description": "Email subject header"},
                "body": {"type": "string", "description": "Email body content"},
            },
            "required": ["recipient", "subject", "body"],
            "additionalProperties": False,
        },
        server_name=SERVER_NAME,
        is_mutation=True,
        requires_hitl=True,
    ),
    MCPToolDefinition(
        name="trigger_webhook",
        description="Dispatch an external HTTP webhook. Hardened with SSRF private network blockers.",
        parameters_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Public destination webhook URL"},
                "payload": {"type": "object", "description": "JSON payload dictionary"},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        server_name=SERVER_NAME,
        is_mutation=True,
        requires_hitl=True,
    ),
    MCPToolDefinition(
        name="list_safe_uploads",
        description="List files safely staged in the validated upload quarantine directory.",
        parameters_schema={
            "type": "object",
            "properties": {
                "extension_filter": {
                    "type": "string",
                    "description": "Optional file extension like .pdf or .md",
                }
            },
            "additionalProperties": False,
        },
        server_name=SERVER_NAME,
        is_mutation=False,
        requires_hitl=False,
    ),
]


async def send_email(recipient: str, subject: str, body: str) -> dict[str, Any]:
    """Simulate or execute validated email dispatch."""
    if not _EMAIL_REGEX.match(recipient.strip()):
        raise ValueError(f"Invalid email address format: {recipient}")

    # Simulated SMTP dispatch logging
    return {
        "status": "SENT",
        "recipient": recipient,
        "subject": subject,
        "characters_sent": len(body),
        "delivery_mode": "SIMULATED_SECURE_GATEWAY",
    }


async def trigger_webhook(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute webhook request after strict SSRF IP check."""
    is_valid, error_msg = _ssrf_validator.validate_url(url)
    if not is_valid:
        raise ValueError(f"SSRF Security Violation: {error_msg}")

    data = payload or {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=data)
            return {
                "status": "DELIVERED",
                "http_status": resp.status_code,
                "response_bytes": len(resp.content),
            }
        except Exception as exc:
            return {"status": "FAILED", "error": str(exc)}


async def list_safe_uploads(extension_filter: str | None = None) -> list[dict[str, Any]]:
    """List files jailed in SAFE_UPLOAD_DIR."""
    import tempfile

    default_safe_dir = str(Path(tempfile.gettempdir()) / "safe_uploads")
    upload_dir_str = os.getenv("SAFE_UPLOAD_DIR", default_safe_dir)
    safe_dir = Path(upload_dir_str).resolve()
    if not safe_dir.exists():
        safe_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for item in safe_dir.iterdir():
        if item.is_file():
            if extension_filter and not item.name.lower().endswith(extension_filter.lower()):
                continue
            results.append(
                {
                    "filename": item.name,
                    "size_bytes": item.stat().st_size,
                    "last_modified": item.stat().st_mtime,
                }
            )
    return results


async def handle_call(tool_name: str, arguments: dict[str, Any]) -> Any:
    if tool_name == "send_email":
        return await send_email(arguments["recipient"], arguments["subject"], arguments["body"])
    elif tool_name == "trigger_webhook":
        return await trigger_webhook(arguments["url"], arguments.get("payload"))
    elif tool_name == "list_safe_uploads":
        return await list_safe_uploads(arguments.get("extension_filter"))
    raise ValueError(f"Unknown tool: {tool_name}")


if __name__ == "__main__":
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
                    out = await handle_call(params.get("name"), params.get("arguments", {}))
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
