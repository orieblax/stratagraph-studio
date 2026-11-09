"""Transactional Outbox and Idempotent SHA-256 Document Chunker."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select, update

from src.modules.rag_etl.domain.repositories import DocumentChunk, IVectorStoreRepository
from src.modules.rag_etl.infrastructure.models import DocumentChunkModel, ETLOutboxModel
from src.shared.database import async_session_factory
from src.shared.logging import get_logger
from src.shared.registry import ILLMProvider

logger = get_logger(__name__)


def compute_chunk_hash(text_content: str) -> str:
    """Compute SHA-256 hash of normalized chunk content."""
    clean = " ".join(text_content.strip().split())
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


class IdempotentOutboxChunker:
    """Orchestrates multi-stage ETL ingestion with Outbox state machine and SHA-256 deduplication."""

    def __init__(
        self,
        vector_repo: IVectorStoreRepository,
        embedding_provider: ILLMProvider,
        session_factory: Any = None,
    ) -> None:
        self.vector_repo = vector_repo
        self.embedding_provider = embedding_provider
        self.session_factory = session_factory or async_session_factory

    def split_text(
        self,
        text_content: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> list[str]:
        """Recursive character-based text splitter."""
        if not text_content:
            return []

        chunks: list[str] = []
        step = max(chunk_size - chunk_overlap, 100)
        for i in range(0, len(text_content), step):
            c = text_content[i : i + chunk_size].strip()
            if c:
                chunks.append(c)
        return chunks

    async def initialize_outbox_record(
        self,
        document_id: str,
        file_name: str,
        file_path: str,
    ) -> str:
        """Create new Transactional Outbox record in PENDING state."""
        outbox_id = str(uuid.uuid4())
        async with self.session_factory() as session, session.begin():
            outbox_entry = ETLOutboxModel(
                id=uuid.UUID(outbox_id),
                document_id=document_id,
                file_name=file_name,
                file_path=file_path,
                chunk_count=0,
                status="PENDING",
            )
            session.add(outbox_entry)
        return outbox_id

    async def update_outbox_status(
        self,
        outbox_id: str,
        status: str,
        *,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Transition Outbox entry status."""
        values: dict[str, Any] = {"status": status}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if error_message is not None:
            values["error_message"] = error_message

        async with self.session_factory() as session, session.begin():
            await session.execute(
                update(ETLOutboxModel)
                .where(ETLOutboxModel.id == uuid.UUID(outbox_id))
                .values(**values)
            )

    async def process_document_etl(
        self,
        outbox_id: str,
        document_id: str,
        raw_text: str | None = None,
        metadata: dict[str, Any] | None = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> list[str]:
        """Execute idempotent chunking, embedding, and repository upsert."""
        meta = metadata or {}

        try:
            # 1. Resolve raw text from input or file path
            if raw_text is None:
                async with self.session_factory() as session:
                    res = await session.execute(
                        select(ETLOutboxModel.file_path).where(
                            ETLOutboxModel.id == uuid.UUID(outbox_id)
                        )
                    )
                    file_path_val = res.scalar()
                if not file_path_val or not Path(file_path_val).exists():
                    raise FileNotFoundError(f"Source file not found: {file_path_val}")
                raw_text = Path(file_path_val).read_text(encoding="utf-8", errors="ignore")

            # 2. Chunking & SHA-256 Hash Computation
            raw_chunks = self.split_text(raw_text, chunk_size, chunk_overlap)
            chunk_hashes = [compute_chunk_hash(c) for c in raw_chunks]

            await self.update_outbox_status(outbox_id, "CHUNKED", chunk_count=len(raw_chunks))

            # 3. Check for existing chunks to avoid redundant embedding computation
            async with self.session_factory() as session:
                existing_res = await session.execute(
                    select(DocumentChunkModel.chunk_hash).where(
                        DocumentChunkModel.chunk_hash.in_(chunk_hashes)
                    )
                )
                existing_hashes = set(existing_res.scalars().all())

            # 4. Generate embeddings only for new hashes
            new_indices = [i for i, h in enumerate(chunk_hashes) if h not in existing_hashes]
            new_texts = [raw_chunks[i] for i in new_indices]

            new_embeddings: list[list[float]] = []
            if new_texts:
                new_embeddings = await self.embedding_provider.generate_embeddings(new_texts)

            # Map embeddings
            embedding_map: dict[str, list[float]] = {}
            for idx, embedding in zip(new_indices, new_embeddings, strict=False):
                embedding_map[chunk_hashes[idx]] = embedding

            # 5. Assemble DocumentChunk domain models
            chunks_to_upsert: list[DocumentChunk] = []
            for idx, (content, chash) in enumerate(zip(raw_chunks, chunk_hashes, strict=False)):
                emb = embedding_map.get(chash, [0.0] * 1536)
                chunks_to_upsert.append(
                    DocumentChunk(
                        document_id=document_id,
                        chunk_index=idx,
                        content=content,
                        metadata={**meta, "outbox_id": outbox_id},
                        embedding=emb,
                        chunk_hash=chash,
                    )
                )

            # 6. Idempotent Repository Upsert
            inserted_ids = await self.vector_repo.upsert_chunks(chunks_to_upsert)

            await self.update_outbox_status(outbox_id, "EMBEDDED_LOCAL")
            logger.info(
                "etl_pipeline_completed",
                document_id=document_id,
                total_chunks=len(raw_chunks),
                reused_chunks=len(existing_hashes),
                new_embeddings=len(new_texts),
            )
            return inserted_ids

        except Exception as exc:
            logger.error("etl_pipeline_failed", outbox_id=outbox_id, error=str(exc))
            await self.update_outbox_status(outbox_id, "FAILED", error_message=str(exc))
            raise
