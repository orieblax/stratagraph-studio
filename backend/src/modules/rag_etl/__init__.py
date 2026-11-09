"""RAG & ETL Module."""

from src.modules.rag_etl.domain.repositories import (
    DocumentChunk,
    ETLOutboxItem,
    IVectorStoreRepository,
    ScoredChunk,
)
from src.modules.rag_etl.infrastructure.chunker_outbox import (
    IdempotentOutboxChunker,
    compute_chunk_hash,
)
from src.modules.rag_etl.infrastructure.models import (
    DocumentChunkModel,
    ETLOutboxModel,
    SemanticCacheModel,
)
from src.modules.rag_etl.infrastructure.postgres_vector_repository import (
    PostgresVectorRepository,
)
from src.modules.rag_etl.infrastructure.reranker import (
    QuantizedCrossEncoderReranker,
)
from src.modules.rag_etl.infrastructure.supabase_repository import (
    SupabaseRepository,
)

__all__ = [
    "DocumentChunk",
    "ScoredChunk",
    "ETLOutboxItem",
    "IVectorStoreRepository",
    "DocumentChunkModel",
    "SemanticCacheModel",
    "ETLOutboxModel",
    "PostgresVectorRepository",
    "SupabaseRepository",
    "IdempotentOutboxChunker",
    "compute_chunk_hash",
    "QuantizedCrossEncoderReranker",
]
