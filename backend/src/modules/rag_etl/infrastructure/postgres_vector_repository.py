"""Concrete PostgreSQL pgvector repository with Reciprocal Rank Fusion (RRF) Hybrid Search."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert

from src.modules.rag_etl.domain.repositories import (
    DocumentChunk,
    IVectorStoreRepository,
    ScoredChunk,
)
from src.modules.rag_etl.infrastructure.models import DocumentChunkModel
from src.shared.database import async_session_factory
from src.shared.logging import get_logger
from src.shared.registry import register_vector_store

logger = get_logger(__name__)


@register_vector_store("postgres_local")
class PostgresVectorRepository(IVectorStoreRepository):
    """Local PostgreSQL pgvector repository supporting HNSW and BM25 RRF."""

    def __init__(self, session_factory: Any = None) -> None:
        self.session_factory = session_factory or async_session_factory

    async def upsert_chunks(self, chunks: list[DocumentChunk]) -> list[str]:
        """Idempotently insert chunks using ON CONFLICT (chunk_hash) DO NOTHING."""
        if not chunks:
            return []

        async with self.session_factory() as session, session.begin():
            records: list[dict[str, Any]] = [
                {
                    "id": uuid.UUID(chunk.id) if isinstance(chunk.id, str) else chunk.id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "metadata": chunk.metadata,
                    "embedding": chunk.embedding,
                    "chunk_hash": chunk.chunk_hash,
                }
                for chunk in chunks
            ]

            stmt = insert(DocumentChunkModel).values(records)
            stmt = stmt.on_conflict_do_nothing(index_elements=["chunk_hash"])
            ret_stmt = stmt.returning(DocumentChunkModel.id)

            result = await session.execute(ret_stmt)
            inserted_ids = [str(row[0]) for row in result.fetchall()]
            return inserted_ids

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        rrf_k: int = 60,
    ) -> list[ScoredChunk]:
        """Perform reciprocal rank fusion between vector cosine search and full-text search."""
        candidate_k = max(top_k * 3, 20)
        vec_rows: list[Any] = []
        bm25_rows: list[Any] = []

        try:
            async with self.session_factory() as session:
                # 1. Vector Search Query (HNSW Cosine Distance)
                cosine_dist = DocumentChunkModel.embedding.cosine_distance(query_embedding)
                vec_stmt = (
                    select(
                        DocumentChunkModel.id,
                        DocumentChunkModel.document_id,
                        DocumentChunkModel.chunk_index,
                        DocumentChunkModel.content,
                        DocumentChunkModel.metadata_,
                        cosine_dist.label("distance"),
                    )
                    .order_by(cosine_dist.asc())
                    .limit(candidate_k)
                )
                vec_res = await session.execute(vec_stmt)
                vec_rows = list(vec_res.fetchall())

                # 2. Full-Text Search Query (Postgres plainto_tsquery + ts_rank_cd)
                # Use raw SQL fragment for tsvector rank
                bm25_stmt = (
                    select(
                        DocumentChunkModel.id,
                        DocumentChunkModel.document_id,
                        DocumentChunkModel.chunk_index,
                        DocumentChunkModel.content,
                        DocumentChunkModel.metadata_,
                        func.ts_rank_cd(
                            text("document_chunks.tsv"),
                            func.plainto_tsquery("english", query_text),
                        ).label("bm25_rank"),
                    )
                    .where(text("document_chunks.tsv @@ plainto_tsquery('english', :q_text)"))
                    .params(q_text=query_text)
                    .order_by(text("bm25_rank DESC"))
                    .limit(candidate_k)
                )
                try:
                    bm25_res = await session.execute(bm25_stmt)
                    bm25_rows = list(bm25_res.fetchall())
                except Exception:
                    # In case table full-text tsquery is empty or not yet generated
                    bm25_rows = []
        except Exception as exc:
            logger.warning("postgres_hybrid_search_db_error", error=str(exc))

        # 3. Reciprocal Rank Fusion Computation
        vector_ranks: dict[str, int] = {}
        vector_scores: dict[str, float] = {}
        chunk_data: dict[str, tuple[str, int, str, dict[str, Any]]] = {}

        for rank, row in enumerate(vec_rows, start=1):
            cid = str(row[0])
            vector_ranks[cid] = rank
            vector_scores[cid] = max(0.0, 1.0 - float(row[5]))
            chunk_data[cid] = (row[1], row[2], row[3], row[4])

        bm25_ranks: dict[str, int] = {}
        bm25_scores: dict[str, float] = {}
        for rank, row in enumerate(bm25_rows, start=1):
            cid = str(row[0])
            bm25_ranks[cid] = rank
            bm25_scores[cid] = float(row[5])
            if cid not in chunk_data:
                chunk_data[cid] = (row[1], row[2], row[3], row[4])

        all_ids = set(vector_ranks.keys()).union(set(bm25_ranks.keys()))
        scored_chunks: list[ScoredChunk] = []

        for cid in all_ids:
            v_rank = vector_ranks.get(cid)
            b_rank = bm25_ranks.get(cid)

            rrf = 0.0
            if v_rank is not None:
                rrf += 1.0 / (rrf_k + v_rank)
            if b_rank is not None:
                rrf += 1.0 / (rrf_k + b_rank)

            doc_id, chunk_idx, content, meta = chunk_data[cid]
            scored_chunks.append(
                ScoredChunk(
                    chunk_id=cid,
                    document_id=doc_id,
                    chunk_index=chunk_idx,
                    content=content,
                    metadata=meta,
                    vector_score=vector_scores.get(cid, 0.0),
                    bm25_score=bm25_scores.get(cid, 0.0),
                    rrf_score=rrf,
                    source_backend="postgres_local",
                )
            )

        scored_chunks.sort(key=lambda x: x.rrf_score, reverse=True)
        return scored_chunks[:top_k]

    async def delete_by_document_id(self, document_id: str) -> int:
        """Delete all chunks for a document ID."""
        async with self.session_factory() as session, session.begin():
            stmt = delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
            res = await session.execute(stmt)
            count = getattr(res, "rowcount", 0)
            return int(count if count is not None else 0)
