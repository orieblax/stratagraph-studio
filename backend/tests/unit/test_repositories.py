"""Unit tests for Strategy Registry, CQRS Bus, and Persistence Domain entities."""

from dataclasses import dataclass

import pytest

from src.modules.databricks_lakehouse.infrastructure.lakehouse_repository import (
    DatabricksLakehouseRepository,
)
from src.modules.rag_etl.domain.repositories import (
    DocumentChunk,
    ETLOutboxItem,
    ScoredChunk,
)
from src.modules.rag_etl.infrastructure.postgres_vector_repository import (
    PostgresVectorRepository,
)
from src.modules.rag_etl.infrastructure.supabase_repository import (
    SupabaseRepository,
)
from src.shared.cqrs import Command, CommandBus, Query, QueryBus
from src.shared.logging import correlation_id_ctx
from src.shared.registry import (
    get_vector_store,
    list_registered_vector_stores,
)


def test_strategy_registry_has_all_three_vector_stores() -> None:
    stores = list_registered_vector_stores()
    assert "postgres_local" in stores
    assert "supabase_cloud" in stores
    assert "databricks_unity_catalog" in stores

    assert get_vector_store("postgres_local") is PostgresVectorRepository
    assert get_vector_store("supabase_cloud") is SupabaseRepository
    assert get_vector_store("databricks_unity_catalog") is DatabricksLakehouseRepository


def test_strategy_registry_raises_descriptive_key_error() -> None:
    with pytest.raises(KeyError, match="Vector Store 'unknown_store' is not registered"):
        get_vector_store("unknown_store")


@dataclass(frozen=True)
class IngestDocumentCommand(Command):
    document_id: str = "doc_101"
    raw_text: str = "Sample content"


@dataclass(frozen=True)
class GetDocumentQuery(Query):
    document_id: str = "doc_101"


@pytest.mark.asyncio
async def test_cqrs_command_bus_execution_and_correlation_propagation() -> None:
    bus = CommandBus()

    async def handle_ingest(cmd: IngestDocumentCommand) -> str:
        # Verify correlation_id was injected into contextvar
        assert correlation_id_ctx.get() == cmd.correlation_id
        return f"Ingested {cmd.document_id}"

    bus.register(IngestDocumentCommand, handle_ingest)
    cmd = IngestDocumentCommand(correlation_id="corr-xyz-789")
    result = await bus.execute(cmd)

    assert result == "Ingested doc_101"


@pytest.mark.asyncio
async def test_cqrs_query_bus_execution() -> None:
    bus = QueryBus()

    async def handle_query(query: GetDocumentQuery) -> dict[str, str]:
        return {"id": query.document_id, "status": "READY"}

    bus.register(GetDocumentQuery, handle_query)
    query = GetDocumentQuery()
    result = await bus.execute(query)

    assert result["id"] == "doc_101"
    assert result["status"] == "READY"


def test_domain_entity_instantiations() -> None:
    chunk = DocumentChunk(
        document_id="doc_01",
        chunk_index=0,
        content="Chunk text",
        metadata={"author": "Team"},
        embedding=[0.1] * 1536,
        chunk_hash="sha256_mock_hash",
    )
    assert len(chunk.embedding) == 1536

    scored = ScoredChunk(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        metadata=chunk.metadata,
        vector_score=0.95,
        bm25_score=1.2,
        rrf_score=0.032,
    )
    assert scored.rrf_score == 0.032

    outbox = ETLOutboxItem(
        id="outbox_1",
        document_id="doc_01",
        file_name="file.pdf",
        file_path="/safe_uploads/file.pdf",
        chunk_count=10,
        status="PENDING",
    )
    assert outbox.status in {"PENDING", "CHUNKED", "EMBEDDED_LOCAL", "SYNCED_DATABRICKS", "FAILED"}
