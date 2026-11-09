"""Databricks SQL Warehouse connection pool and cold-start wake-up manager."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable, Coroutine
from typing import Any

from databricks import sql
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.shared.ephemeral_secrets import EphemeralSecretVault
from src.shared.logging import get_logger

logger = get_logger(__name__)

StatusCallback = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


class SQLWarehouseColdStartManager:
    """Manages connections to Databricks SQL Warehouse with cold-start detection and status events."""

    def __init__(
        self,
        server_hostname: str | None = None,
        http_path: str | None = None,
        access_token: str | None = None,
        status_callback: StatusCallback | None = None,
    ) -> None:
        self._server_hostname = server_hostname
        self._http_path = http_path
        self._access_token = access_token
        self.status_callback = status_callback

    def _resolve_connection_params(self) -> tuple[str, str, str]:
        host_val = (
            self._server_hostname
            or EphemeralSecretVault.get_secret_value(
                "DATABRICKS_HOST", os.getenv("DATABRICKS_HOST", "")
            )
            or ""
        )
        host = host_val[len("https://") :] if host_val.startswith("https://") else host_val
        host = host.rstrip("/")

        http_path = (
            self._http_path
            or os.getenv("DATABRICKS_HTTP_PATH")
            or f"/sql/1.0/warehouses/{os.getenv('DATABRICKS_SQL_WAREHOUSE_ID', '')}"
        )

        token = self._access_token or EphemeralSecretVault.get_secret_value(
            "DATABRICKS_TOKEN", os.getenv("DATABRICKS_TOKEN", "")
        )

        if not host or not token:
            raise ValueError(
                "Databricks Host and Access Token must be provided via UI ConfigPanel or environment."
            )

        return host, http_path, token

    async def execute_query_with_retry(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        *,
        max_attempts: int = 6,
        timeout_seconds: int = 120,
    ) -> list[dict[str, Any]]:
        """Execute a query on Databricks SQL Warehouse with automatic retry for cluster spin-up."""
        host, http_path, token = self._resolve_connection_params()
        start_time = time.time()

        attempt_count = 0

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=2, min=3, max=30),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                attempt_count += 1
                try:
                    if attempt_count > 1 and self.status_callback:
                        await self.status_callback(
                            "Warming up Databricks SQL Warehouse...",
                            {
                                "attempt": attempt_count,
                                "elapsed_seconds": round(time.time() - start_time, 1),
                                "server_hostname": host,
                            },
                        )

                    # Offload synchronous databricks-sql-connector blocking call to worker thread
                    def _sync_exec() -> list[dict[str, Any]]:
                        with (
                            sql.connect(
                                server_hostname=host,
                                http_path=http_path,
                                access_token=token,
                                _user_agent_entry="StrataGraph-Studio-ColdStartManager/1.0",
                            ) as connection,
                            connection.cursor() as cursor,
                        ):
                            cursor.execute(query, parameters)
                            if cursor.description is None:
                                return []
                            columns = [desc[0] for desc in cursor.description]
                            rows = cursor.fetchall()
                            return [dict(zip(columns, row, strict=False)) for row in rows]

                    result = await asyncio.wait_for(
                        asyncio.to_thread(_sync_exec), timeout=float(timeout_seconds)
                    )
                    return result

                except Exception as exc:
                    error_msg = str(exc).lower()
                    # Check if error is related to warehouse starting up or temporarily unavailable
                    if any(
                        s in error_msg
                        for s in (
                            "starting",
                            "stopped",
                            "provisioning",
                            "timeout",
                            "temporarily unavailable",
                        )
                    ):
                        logger.warning(
                            "databricks_sql_warehouse_warming",
                            attempt=attempt_count,
                            elapsed=round(time.time() - start_time, 1),
                            error=str(exc),
                        )
                        if self.status_callback:
                            await self.status_callback(
                                "Warming up Databricks SQL Warehouse...",
                                {
                                    "status": "WARMING",
                                    "attempt": attempt_count,
                                    "error": str(exc),
                                },
                            )
                        raise
                    else:
                        logger.error("databricks_sql_query_failed", query=query, error=str(exc))
                        raise

        return []
