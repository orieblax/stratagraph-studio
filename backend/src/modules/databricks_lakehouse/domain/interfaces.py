"""Databricks Lakehouse Medallion and Vector Search domain interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class VolumeFile:
    """Represents a raw document file landed in a Unity Catalog Volume."""

    volume_path: str
    file_name: str
    size_bytes: int
    uploaded_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class BronzeDocument:
    """Represents raw extracted text and metadata stored in the Bronze Delta table."""

    document_id: str
    volume_file_path: str
    raw_content: str
    metadata: dict[str, Any]
    ingested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class SilverChunk:
    """Represents cleaned, PII-scrubbed, deduplicated chunks in the Silver Delta table."""

    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    chunk_hash: str
    processed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class GoldSyncStatus:
    """Status of Delta Sync into Databricks Vector Search Index."""

    index_name: str
    sync_status: str  # SYNCING, READY, FAILED
    total_indexed_chunks: int
    last_sync_time: datetime = field(default_factory=datetime.utcnow)
    details: dict[str, Any] = field(default_factory=dict)


class ILakehouseRepository(Protocol):
    """Protocol for interacting with the Databricks Medallion Lakehouse and Vector Search."""

    async def upload_to_volume(
        self,
        local_file_path: str,
        target_filename: str,
        *,
        catalog: str | None = None,
        schema: str | None = None,
        volume: str | None = None,
    ) -> VolumeFile:
        """Upload raw file to Unity Catalog Volume."""
        ...

    async def ingest_to_bronze(
        self,
        document_id: str,
        volume_file_path: str,
        raw_content: str,
        metadata: dict[str, Any],
    ) -> BronzeDocument:
        """Append raw document content to Bronze Delta table."""
        ...

    async def sync_to_silver(
        self,
        chunks: list[SilverChunk],
    ) -> int:
        """Merge cleaned chunks into Silver Delta table (idempotent by chunk_hash)."""
        ...

    async def trigger_gold_vector_sync(
        self,
        index_name: str | None = None,
    ) -> GoldSyncStatus:
        """Trigger Delta Sync on the Databricks Vector Search Index."""
        ...

    async def search_gold_vectors(
        self,
        query_text: str,
        query_vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Query Databricks Gold Vector Search Index."""
        ...
