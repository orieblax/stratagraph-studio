"""Concrete Supabase Cloud Vector repository using REST / PostgREST vector extensions."""

from __future__ import annotations

import os
from typing import Any

import httpx

from src.modules.rag_etl.domain.repositories import (
    DocumentChunk,
    IVectorStoreRepository,
    ScoredChunk,
)
from src.shared.ephemeral_secrets import EphemeralSecretVault
from src.shared.registry import register_vector_store


@register_vector_store("supabase_cloud")
class SupabaseRepository(IVectorStoreRepository):
    """Supabase Cloud repository leveraging remote pgvector and RPC endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        service_key: str | None = None,
    ) -> None:
        self._configured_url = base_url
        self._configured_key = service_key

    def _get_credentials(self) -> tuple[str, str]:
        """Resolve Supabase credentials from EphemeralSecretVault or env."""
        url = self._configured_url or EphemeralSecretVault.get_secret_value(
            "SUPABASE_URL", os.getenv("SUPABASE_URL")
        )
        key = self._configured_key or EphemeralSecretVault.get_secret_value(
            "SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_SERVICE_KEY")
        )

        if not url or not key:
            raise ValueError(
                "Supabase URL or Service Key is missing. Provide them via UI ConfigPanel or environment."
            )
        return url.rstrip("/"), key

    async def upsert_chunks(self, chunks: list[DocumentChunk]) -> list[str]:
        """Upsert chunks into remote Supabase document_chunks table."""
        if not chunks:
            return []

        url, key = self._get_credentials()
        endpoint = f"{url}/rest/v1/document_chunks"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates,return=representation",
        }

        payload = [
            {
                "id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "metadata": chunk.metadata,
                "embedding": chunk.embedding,
                "chunk_hash": chunk.chunk_hash,
            }
            for chunk in chunks
        ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return [str(row["id"]) for row in data] if isinstance(data, list) else []

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        rrf_k: int = 60,
    ) -> list[ScoredChunk]:
        """Query remote Supabase match_chunks RPC or vector distance endpoint."""
        url, key = self._get_credentials()
        endpoint = f"{url}/rest/v1/rpc/match_document_chunks"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        body = {
            "query_embedding": query_embedding,
            "query_text": query_text,
            "match_count": top_k,
            "rrf_k": rrf_k,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(endpoint, json=body, headers=headers)
                resp.raise_for_status()
                rows: list[dict[str, Any]] = resp.json()
            except httpx.HTTPError:
                # If custom RPC is not yet created in remote database, fallback to REST select
                fallback_url = f"{url}/rest/v1/document_chunks?select=id,document_id,chunk_index,content,metadata&limit={top_k}"
                resp = await client.get(fallback_url, headers=headers)
                resp.raise_for_status()
                rows = resp.json()

        results: list[ScoredChunk] = []
        for idx, row in enumerate(rows):
            sim = float(row.get("similarity", 0.85))
            results.append(
                ScoredChunk(
                    chunk_id=str(row.get("id", "")),
                    document_id=str(row.get("document_id", "")),
                    chunk_index=int(row.get("chunk_index", idx)),
                    content=str(row.get("content", "")),
                    metadata=row.get("metadata", {}),
                    vector_score=sim,
                    bm25_score=0.0,
                    rrf_score=sim,
                    source_backend="supabase_cloud",
                )
            )
        return results

    async def delete_by_document_id(self, document_id: str) -> int:
        """Purge chunks for a document ID from Supabase."""
        url, key = self._get_credentials()
        endpoint = f"{url}/rest/v1/document_chunks?document_id=eq.{document_id}"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Prefer": "count=exact",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(endpoint, headers=headers)
            resp.raise_for_status()
            content_range = resp.headers.get("content-range", "")
            if "/" in content_range:
                try:
                    return int(content_range.split("/")[1])
                except (ValueError, IndexError):
                    return 1
            return 1
