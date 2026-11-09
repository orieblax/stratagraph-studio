"""Concrete Databricks Lakehouse Medallion and Vector Search repository."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from databricks.sdk import WorkspaceClient

from src.modules.databricks_lakehouse.domain.interfaces import (
    BronzeDocument,
    GoldSyncStatus,
    ILakehouseRepository,
    SilverChunk,
    VolumeFile,
)
from src.modules.databricks_lakehouse.infrastructure.cold_start_manager import (
    SQLWarehouseColdStartManager,
)
from src.modules.rag_etl.domain.repositories import (
    DocumentChunk,
    IVectorStoreRepository,
    ScoredChunk,
)
from src.shared.ephemeral_secrets import EphemeralSecretVault
from src.shared.logging import get_logger
from src.shared.registry import register_vector_store

logger = get_logger(__name__)


@register_vector_store("databricks_unity_catalog")
class DatabricksLakehouseRepository(ILakehouseRepository, IVectorStoreRepository):
    """Integrates Unity Catalog Volumes, Medallion Delta tables, and Vector Search."""

    def __init__(
        self,
        workspace_client: WorkspaceClient | None = None,
        cold_start_manager: SQLWarehouseColdStartManager | None = None,
    ) -> None:
        self._workspace_client = workspace_client
        self._cold_start_manager = cold_start_manager or SQLWarehouseColdStartManager()

    def _get_workspace_client(self) -> WorkspaceClient:
        if self._workspace_client is not None:
            return self._workspace_client

        host = EphemeralSecretVault.get_secret_value(
            "DATABRICKS_HOST", os.getenv("DATABRICKS_HOST")
        )
        token = EphemeralSecretVault.get_secret_value(
            "DATABRICKS_TOKEN", os.getenv("DATABRICKS_TOKEN")
        )

        if not host or not token:
            raise ValueError(
                "Databricks Host and Token are required to initialize WorkspaceClient."
            )

        return WorkspaceClient(host=host, token=token)

    def _get_namespace(
        self,
        catalog: str | None = None,
        schema: str | None = None,
        volume: str | None = None,
    ) -> tuple[str, str, str]:
        c = catalog or os.getenv("DATABRICKS_CATALOG", "stratagraph_catalog")
        s = schema or os.getenv("DATABRICKS_SCHEMA", "agent_analytics")
        v = volume or os.getenv("DATABRICKS_VOLUME", "raw_ingest_volume")

        # Sanitize SQL identifiers (alphanumeric and underscores only)
        import re

        clean_c = re.sub(r"[^a-zA-Z0-9_]", "", c or "")
        clean_s = re.sub(r"[^a-zA-Z0-9_]", "", s or "")
        clean_v = re.sub(r"[^a-zA-Z0-9_]", "", v or "")
        return clean_c, clean_s, clean_v

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
        cat, sch, vol = self._get_namespace(catalog, schema, volume)
        volume_path = f"/Volumes/{cat}/{sch}/{vol}/{target_filename}"
        w = self._get_workspace_client()

        file_path = Path(local_file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_file_path}")

        size_bytes = file_path.stat().st_size

        def _upload() -> None:
            with open(file_path, "rb") as f:
                w.files.upload(volume_path, f, overwrite=True)

        await asyncio.to_thread(_upload)
        logger.info("uploaded_to_unity_catalog_volume", path=volume_path, size=size_bytes)
        return VolumeFile(volume_path=volume_path, file_name=target_filename, size_bytes=size_bytes)

    async def ingest_to_bronze(
        self,
        document_id: str,
        volume_file_path: str,
        raw_content: str,
        metadata: dict[str, Any],
    ) -> BronzeDocument:
        """Insert raw content into bronze_documents Delta table."""
        cat, sch, _ = self._get_namespace()
        bronze_table = f"{cat}.{sch}.bronze_documents"

        query = f"""
            INSERT INTO {bronze_table} (document_id, volume_file_path, raw_content, metadata, ingested_at)
            VALUES (:document_id, :volume_file_path, :raw_content, :metadata, CURRENT_TIMESTAMP())
        """  # nosec B608
        params = {
            "document_id": document_id,
            "volume_file_path": volume_file_path,
            "raw_content": raw_content,
            "metadata": json.dumps(metadata),
        }
        await self._cold_start_manager.execute_query_with_retry(query, params)
        return BronzeDocument(
            document_id=document_id,
            volume_file_path=volume_file_path,
            raw_content=raw_content,
            metadata=metadata,
        )

    async def sync_to_silver(self, chunks: list[SilverChunk]) -> int:
        """Idempotently MERGE deduplicated chunks into silver_chunks Delta table."""
        if not chunks:
            return 0

        cat, sch, _ = self._get_namespace()
        silver_table = f"{cat}.{sch}.silver_chunks"

        inserted_count = 0
        for chunk in chunks:
            query = f"""
                MERGE INTO {silver_table} AS target
                USING (
                    SELECT
                        :chunk_id AS chunk_id,
                        :document_id AS document_id,
                        :chunk_index AS chunk_index,
                        :content AS content,
                        :metadata AS metadata,
                        :chunk_hash AS chunk_hash
                ) AS source
                ON target.chunk_hash = source.chunk_hash
                WHEN NOT MATCHED THEN INSERT (
                    chunk_id, document_id, chunk_index, content, metadata, chunk_hash, processed_at
                ) VALUES (
                    source.chunk_id, source.document_id, source.chunk_index, source.content,
                    source.metadata, source.chunk_hash, CURRENT_TIMESTAMP()
                )
            """
            params = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "metadata": json.dumps(chunk.metadata),
                "chunk_hash": chunk.chunk_hash,
            }
            await self._cold_start_manager.execute_query_with_retry(query, params)
            inserted_count += 1

        return inserted_count

    async def trigger_gold_vector_sync(
        self,
        index_name: str | None = None,
    ) -> GoldSyncStatus:
        """Trigger Delta Sync on Databricks Vector Search Index."""
        idx = str(
            index_name
            or os.getenv(
                "DATABRICKS_VECTOR_SEARCH_INDEX",
                "stratagraph_catalog.agent_analytics.gold_vector_index",
            )
        )
        w = self._get_workspace_client()

        def _sync() -> Any:
            try:
                return w.vector_search_indexes.sync_index(index_name=idx)
            except Exception as exc:
                logger.warning("databricks_vector_index_sync_triggered", index=idx, error=str(exc))
                return None

        await asyncio.to_thread(_sync)
        return GoldSyncStatus(index_name=idx, sync_status="SYNCING", total_indexed_chunks=0)

    async def search_gold_vectors(
        self,
        query_text: str,
        query_vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Query Databricks Vector Search Index."""
        _ = query_text
        idx = str(
            os.getenv(
                "DATABRICKS_VECTOR_SEARCH_INDEX",
                "stratagraph_catalog.agent_analytics.gold_vector_index",
            )
        )
        w = self._get_workspace_client()

        def _query() -> list[dict[str, Any]]:
            try:
                resp = w.vector_search_indexes.query_index(
                    index_name=idx,
                    query_vector=query_vector,
                    num_results=top_k,
                    columns=["chunk_id", "document_id", "chunk_index", "content", "metadata"],
                )
                if hasattr(resp, "result") and resp.result and hasattr(resp.result, "data_array"):
                    data = resp.result.data_array
                    if (
                        data is not None
                        and hasattr(resp, "manifest")
                        and resp.manifest
                        and hasattr(resp.manifest, "columns")
                        and resp.manifest.columns is not None
                    ):
                        columns = [str(c.name) for c in resp.manifest.columns if hasattr(c, "name")]
                        return [dict(zip(columns, row, strict=False)) for row in data]
                return []
            except Exception as exc:
                logger.error("databricks_vector_search_error", index=idx, error=str(exc))
                return []

        return await asyncio.to_thread(_query)

    # IVectorStoreRepository Implementation (Protocol bridge)
    async def upsert_chunks(self, chunks: list[DocumentChunk]) -> list[str]:
        silver_chunks = [
            SilverChunk(
                chunk_id=c.id,
                document_id=c.document_id,
                chunk_index=c.chunk_index,
                content=c.content,
                metadata=c.metadata,
                chunk_hash=c.chunk_hash,
            )
            for c in chunks
        ]
        await self.sync_to_silver(silver_chunks)
        await self.trigger_gold_vector_sync()
        return [c.id for c in chunks]

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        rrf_k: int = 60,
    ) -> list[ScoredChunk]:
        _ = rrf_k
        raw_results = await self.search_gold_vectors(query_text, query_embedding, top_k=top_k)
        scored: list[ScoredChunk] = []
        for idx, row in enumerate(raw_results):
            score = float(row.get("score", 0.90 - idx * 0.05))
            meta_raw = row.get("metadata", "{}")
            meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
            scored.append(
                ScoredChunk(
                    chunk_id=str(row.get("chunk_id", "")),
                    document_id=str(row.get("document_id", "")),
                    chunk_index=int(row.get("chunk_index", idx)),
                    content=str(row.get("content", "")),
                    metadata=meta,
                    vector_score=score,
                    bm25_score=0.0,
                    rrf_score=score,
                    source_backend="databricks_unity_catalog",
                )
            )
        return scored

    async def delete_by_document_id(self, document_id: str) -> int:
        cat, sch, _ = self._get_namespace()
        del_bronze = f"DELETE FROM {cat}.{sch}.bronze_documents WHERE document_id = :doc_id"  # nosec B608
        del_silver = f"DELETE FROM {cat}.{sch}.silver_chunks WHERE document_id = :doc_id"  # nosec B608
        params = {"doc_id": document_id}
        await self._cold_start_manager.execute_query_with_retry(del_bronze, params)
        await self._cold_start_manager.execute_query_with_retry(del_silver, params)
        return 1
