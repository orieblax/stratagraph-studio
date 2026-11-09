"""Shared kernel containing protocols, registries, ephemeral vault, logging, and database pooling."""

from src.shared.cqrs import Command, CommandBus, Query, QueryBus
from src.shared.ephemeral_secrets import EphemeralSecretVault
from src.shared.logging import configure_logging, get_logger
from src.shared.registry import (
    get_llm_provider,
    get_node,
    get_vector_store,
    register_llm_provider,
    register_node,
    register_vector_store,
)

__all__ = [
    "register_llm_provider",
    "register_vector_store",
    "register_node",
    "get_llm_provider",
    "get_vector_store",
    "get_node",
    "EphemeralSecretVault",
    "configure_logging",
    "get_logger",
    "Command",
    "Query",
    "CommandBus",
    "QueryBus",
]
