"""Two-Tier PostgreSQL pgvector Semantic Cache (Exact Hash + Cosine Similarity)."""

from __future__ import annotations

import hashlib
import time
from typing import Any

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert

from src.modules.cost_optimization.domain.interfaces import CacheResult, ISemanticCache
from src.modules.rag_etl.infrastructure.models import SemanticCacheModel
from src.shared.database import async_session_factory
from src.shared.logging import get_logger

logger = get_logger(__name__)


def compute_exact_hash(prompt: str, config_hash: str) -> str:
    """Generate SHA-256 hash from normalized prompt and configuration hash."""
    normalized = " ".join(prompt.strip().lower().split())
    raw = f"{normalized}:{config_hash}".encode()
    return hashlib.sha256(raw).hexdigest()


class TwoTierPgVectorCache(ISemanticCache):
    """Enforces Tier-1 0ms Exact SHA-256 match followed by Tier-2 pgvector cosine similarity."""

    _shared_mem_cache: dict[str, str] = {}

    def __init__(self, session_factory: Any = None) -> None:
        self.session_factory = session_factory or async_session_factory

    async def get(
        self,
        prompt: str,
        query_embedding: list[float],
        config_hash: str,
        *,
        threshold: float = 0.92,
    ) -> CacheResult:
        """Query Tier 1 (exact hash) and Tier 2 (pgvector cosine similarity)."""
        start_time = time.time()
        exact_h = compute_exact_hash(prompt, config_hash)

        # 1. Tier 1 Memory L1 fast path
        if exact_h in self._shared_mem_cache:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return CacheResult(
                hit=True,
                tier="exact",
                cached_response=self._shared_mem_cache[exact_h],
                similarity_score=1.0,
                latency_ms=elapsed_ms,
                cost_usd=0.0,
            )

        try:
            async with self.session_factory() as session:
                # 1. Tier 1: Exact Hash Match
                stmt_tier1 = select(
                    SemanticCacheModel.id,
                    SemanticCacheModel.response,
                ).where(
                    SemanticCacheModel.exact_hash == exact_h,
                    SemanticCacheModel.config_hash == config_hash,
                )
                res_t1 = await session.execute(stmt_tier1)
                row_t1 = res_t1.first()

                if row_t1 is not None:
                    cache_id, response_text = row_t1
                    self._shared_mem_cache[exact_h] = response_text
                    # Increment hit count asynchronously
                    await session.execute(
                        update(SemanticCacheModel)
                        .where(SemanticCacheModel.id == cache_id)
                        .values(hit_count=SemanticCacheModel.hit_count + 1)
                    )
                    await session.commit()

                    elapsed_ms = round((time.time() - start_time) * 1000, 2)
                    logger.info("semantic_cache_tier1_hit", exact_hash=exact_h, latency_ms=elapsed_ms)
                    return CacheResult(
                        hit=True,
                        tier="exact",
                        cached_response=response_text,
                        similarity_score=1.0,
                        latency_ms=elapsed_ms,
                        cost_usd=0.0,
                    )

                # 2. Tier 2: Semantic Cosine Search via pgvector
                cosine_dist = SemanticCacheModel.embedding.cosine_distance(query_embedding)
                stmt_tier2 = (
                    select(
                        SemanticCacheModel.id,
                        SemanticCacheModel.response,
                        cosine_dist.label("distance"),
                    )
                    .where(SemanticCacheModel.config_hash == config_hash)
                    .order_by(cosine_dist.asc())
                    .limit(1)
                )
                res_t2 = await session.execute(stmt_tier2)
                row_t2 = res_t2.first()

                if row_t2 is not None:
                    cache_id, response_text, dist = row_t2
                    similarity = max(0.0, 1.0 - float(dist))

                    if similarity >= threshold:
                        await session.execute(
                            update(SemanticCacheModel)
                            .where(SemanticCacheModel.id == cache_id)
                            .values(hit_count=SemanticCacheModel.hit_count + 1)
                        )
                        await session.commit()

                        elapsed_ms = round((time.time() - start_time) * 1000, 2)
                        logger.info(
                            "semantic_cache_tier2_hit",
                            similarity=round(similarity, 4),
                            latency_ms=elapsed_ms,
                        )
                        return CacheResult(
                            hit=True,
                            tier="semantic",
                            cached_response=response_text,
                            similarity_score=round(similarity, 4),
                            latency_ms=elapsed_ms,
                            cost_usd=0.0,
                        )
        except Exception as exc:
            logger.warning("semantic_cache_lookup_failed", error=str(exc))

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return CacheResult(
            hit=False,
            tier=None,
            cached_response=None,
            similarity_score=0.0,
            latency_ms=elapsed_ms,
            cost_usd=0.0,
        )

    async def set(
        self,
        prompt: str,
        response: str,
        embedding: list[float],
        config_hash: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store exact hash and embedding vector in cache."""
        exact_h = compute_exact_hash(prompt, config_hash)
        self._shared_mem_cache[exact_h] = response

        try:
            async with self.session_factory() as session, session.begin():
                stmt = insert(SemanticCacheModel).values(
                    exact_hash=exact_h,
                    prompt=prompt,
                    config_hash=config_hash,
                    response=response,
                    metadata=metadata or {},
                    embedding=embedding,
                    hit_count=0,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["exact_hash"],
                    set_={
                        "response": stmt.excluded.response,
                        "updated_at": text("NOW()"),
                    },
                )
                await session.execute(stmt)
        except Exception as exc:
            logger.warning("semantic_cache_set_failed", error=str(exc))

    async def flush(self, config_hash: str | None = None) -> int:
        """Delete entries matching config_hash or clear entire cache."""
        self._shared_mem_cache.clear()
        try:
            async with self.session_factory() as session, session.begin():
                stmt = delete(SemanticCacheModel)
                if config_hash:
                    stmt = stmt.where(SemanticCacheModel.config_hash == config_hash)
                res = await session.execute(stmt)
                count = getattr(res, "rowcount", 0)
                return int(count if count is not None else 0)
        except Exception as exc:
            logger.warning("semantic_cache_flush_failed", error=str(exc))
            return 0
