"""Async SQLAlchemy 2.0 database engine and session management."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://stratagraph:stratagraph_secure_password@localhost:5432/stratagraph_studio"
)

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
_IS_TESTING = os.getenv("ENVIRONMENT") == "testing"

# Configure SQLAlchemy 2.0 Async Engine with robust pooling
# Use NullPool under test environments so per-test event loops never share asyncpg connections.
engine: AsyncEngine = (
    create_async_engine(
        DATABASE_URL,
        poolclass=NullPool,
        echo=False,
        future=True,
    )
    if _IS_TESTING
    else create_async_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,
        future=True,
    )
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base class with native SQLAlchemy 2.0 type annotations."""

    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency and async context generator for database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
