"""Pragmatic CQRS Command and Query Bus dispatchers with correlation propagation."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, TypeVar

from src.shared.logging import correlation_id_ctx

TCommand = TypeVar("TCommand", bound="Command")
TQuery = TypeVar("TQuery", bound="Query")
TResult = TypeVar("TResult")


@dataclass(frozen=True)
class Command:
    """Base CQRS Command representing a state mutation."""

    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class Query:
    """Base CQRS Query representing a read operation."""

    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))


CommandHandlerFunc = Callable[[TCommand], Coroutine[Any, Any, TResult]]
QueryHandlerFunc = Callable[[TQuery], Coroutine[Any, Any, TResult]]


class CommandBus:
    """In-memory async Command dispatcher."""

    def __init__(self) -> None:
        self._handlers: dict[type[Command], CommandHandlerFunc[Any, Any]] = {}

    def register(
        self, command_type: type[TCommand], handler: CommandHandlerFunc[TCommand, TResult]
    ) -> None:
        """Register an async handler for a given Command type."""
        self._handlers[command_type] = handler

    async def execute(self, command: Command) -> Any:
        """Execute a command through its registered handler."""
        cmd_type = type(command)
        if cmd_type not in self._handlers:
            raise KeyError(f"No handler registered for command: {cmd_type.__name__}")

        # Propagate correlation ID to context
        token = correlation_id_ctx.set(command.correlation_id)
        try:
            return await self._handlers[cmd_type](command)
        finally:
            correlation_id_ctx.reset(token)


class QueryBus:
    """In-memory async Query dispatcher."""

    def __init__(self) -> None:
        self._handlers: dict[type[Query], QueryHandlerFunc[Any, Any]] = {}

    def register(
        self, query_type: type[TQuery], handler: QueryHandlerFunc[TQuery, TResult]
    ) -> None:
        """Register an async handler for a given Query type."""
        self._handlers[query_type] = handler

    async def execute(self, query: Query) -> Any:
        """Execute a query through its registered handler."""
        q_type = type(query)
        if q_type not in self._handlers:
            raise KeyError(f"No handler registered for query: {q_type.__name__}")

        token = correlation_id_ctx.set(query.correlation_id)
        try:
            return await self._handlers[q_type](query)
        finally:
            correlation_id_ctx.reset(token)
