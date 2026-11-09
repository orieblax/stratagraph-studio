"""Domain models and repository interfaces for RAG & ETL."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class DocumentChunk:
    """Represents a chunked and embedded document unit."""

    document_id: str
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    embedding: list[float]
    chunk_hash: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class ScoredChunk:
    """Represents a retrieved document chunk with retrieval scores."""

    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float | None = None
    source_backend: str = "postgres_local"


@dataclass(frozen=True)
class ETLOutboxItem:
    """Represents a transactional outbox entry for file ingestion."""

    id: str
    document_id: str
    file_name: str
    file_path: str
    chunk_count: int
    status: str  # PENDING, CHUNKED, EMBEDDED_LOCAL, SYNCED_DATABRICKS, FAILED
    error_message: str | None = None
    retry_count: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class IVectorStoreRepository(Protocol):
    """Protocol for bulk vector storage and hybrid retrieval operations."""

    async def upsert_chunks(self, chunks: list[DocumentChunk]) -> list[str]:
        """Idempotently upsert document chunks by their SHA-256 chunk_hash."""
        ...

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        rrf_k: int = 60,
    ) -> list[ScoredChunk]:
        """Execute hybrid search combining vector cosine similarity and full-text search."""
        ...

    async def delete_by_document_id(self, document_id: str) -> int:
        """Purge all chunks associated with a document ID."""
        ...
