"""Strategy and Factory Registry governed by native Python typing.Protocol interfaces."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class ILLMProvider(Protocol):
    """Protocol for dynamic LLM Providers (OpenAI, Anthropic, Ollama, Databricks)."""

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Any: ...

    async def generate_embeddings(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]: ...


@runtime_checkable
class IVectorStore(Protocol):
    """Protocol for bulk vector and hybrid retrieval repositories."""

    async def upsert_chunks(self, chunks: list[Any]) -> list[str]: ...

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        rrf_k: int = 60,
    ) -> list[Any]: ...

    async def delete_by_document_id(self, document_id: str) -> int: ...


@runtime_checkable
class IGraphNode(Protocol):
    """Protocol for LangGraph workflow execution nodes."""

    async def __call__(self, state: dict[str, Any], config: Any = None) -> dict[str, Any]: ...


# Internal Registries
_LLM_PROVIDERS: dict[str, type[ILLMProvider]] = {}
_VECTOR_STORES: dict[str, type[IVectorStore]] = {}
_GRAPH_NODES: dict[str, Any] = {}


def register_llm_provider(name: str) -> Callable[[type[T]], type[T]]:
    """Decorator to register an LLM provider implementation."""

    def decorator(cls: type[T]) -> type[T]:
        _LLM_PROVIDERS[name.lower()] = cls  # type: ignore[assignment]
        return cls

    return decorator


def register_vector_store(name: str) -> Callable[[type[T]], type[T]]:
    """Decorator to register a Vector Store repository implementation."""

    def decorator(cls: type[T]) -> type[T]:
        _VECTOR_STORES[name.lower()] = cls  # type: ignore[assignment]
        return cls

    return decorator


def register_node(name: str) -> Callable[[T], T]:
    """Decorator to register a LangGraph node executable or class."""

    def decorator(obj: T) -> T:
        _GRAPH_NODES[name] = obj
        return obj

    return decorator


def get_llm_provider(name: str) -> type[ILLMProvider]:
    """Retrieve an LLM provider class by identifier."""
    key = name.lower()
    if key not in _LLM_PROVIDERS:
        available = ", ".join(f"'{k}'" for k in sorted(_LLM_PROVIDERS.keys()))
        raise KeyError(
            f"LLM Provider '{name}' is not registered. Registered providers: [{available}]"
        )
    return _LLM_PROVIDERS[key]


def get_vector_store(name: str) -> type[IVectorStore]:
    """Retrieve a Vector Store repository class by identifier."""
    key = name.lower()
    if key not in _VECTOR_STORES:
        available = ", ".join(f"'{k}'" for k in sorted(_VECTOR_STORES.keys()))
        raise KeyError(f"Vector Store '{name}' is not registered. Registered stores: [{available}]")
    return _VECTOR_STORES[key]


def get_node(name: str) -> Any:
    """Retrieve a LangGraph node by identifier."""
    if name not in _GRAPH_NODES:
        available = ", ".join(f"'{k}'" for k in sorted(_GRAPH_NODES.keys()))
        raise KeyError(f"Graph Node '{name}' is not registered. Registered nodes: [{available}]")
    return _GRAPH_NODES[name]


def list_registered_llm_providers() -> list[str]:
    """List all registered LLM provider keys."""
    return sorted(_LLM_PROVIDERS.keys())


def list_registered_vector_stores() -> list[str]:
    """List all registered Vector Store keys."""
    return sorted(_VECTOR_STORES.keys())


def list_registered_nodes() -> list[str]:
    """List all registered Graph Node keys."""
    return sorted(_GRAPH_NODES.keys())
