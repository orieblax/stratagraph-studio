"""Integration test fixtures isolating shared PostgreSQL state between tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text

from src.shared.database import engine

_INTEGRATION_TABLES = (
    "document_chunks, semantic_cache, etl_outbox, "
    "checkpoints, checkpoint_blobs, checkpoint_writes"
)
_postgres_available: bool | None = None


async def _truncate_integration_tables() -> None:
    """Truncate shared integration tables when PostgreSQL is reachable."""
    global _postgres_available
    if _postgres_available is False:
        return

    try:
        async with asyncio.timeout(3.0), engine.begin() as conn:
            await conn.execute(
                text(f"TRUNCATE TABLE {_INTEGRATION_TABLES} RESTART IDENTITY CASCADE")
            )
        _postgres_available = True
    except Exception:
        _postgres_available = False


@pytest.fixture(autouse=True)
async def isolate_integration_database() -> AsyncIterator[None]:
    """Reset PostgreSQL tables before and after each integration test if DB is live."""
    await _truncate_integration_tables()
    yield
    await _truncate_integration_tables()
