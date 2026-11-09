-- ==============================================================================
-- StrataGraph Studio - PostgreSQL 16 + pgvector Initialization
-- ==============================================================================

-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 2. Document Chunks Table (RAG & Hybrid Search)
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(255) NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536),
    chunk_hash VARCHAR(64) NOT NULL UNIQUE,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indices for Hybrid Search (HNSW Cosine + Full Text Search GIN)
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_document_chunks_tsv 
    ON document_chunks USING gin (tsv);

CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id 
    ON document_chunks (document_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_hash 
    ON document_chunks (chunk_hash);

-- 3. Two-Tier Semantic Cache Table
CREATE TABLE IF NOT EXISTS semantic_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exact_hash VARCHAR(64) NOT NULL UNIQUE,
    prompt TEXT NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    response TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536) NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_semantic_cache_exact_hash 
    ON semantic_cache (exact_hash);

CREATE INDEX IF NOT EXISTS idx_semantic_cache_config_hash 
    ON semantic_cache (config_hash);

CREATE INDEX IF NOT EXISTS idx_semantic_cache_embedding 
    ON semantic_cache USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 4. Transactional Outbox Table for Idempotent ETL Pipeline
CREATE TABLE IF NOT EXISTS etl_outbox (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(255) NOT NULL,
    file_name VARCHAR(512) NOT NULL,
    file_path VARCHAR(1024) NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    -- Allowed statuses: PENDING, CHUNKED, EMBEDDED_LOCAL, SYNCED_DATABRICKS, FAILED
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_etl_outbox_status 
    ON etl_outbox (status);

CREATE INDEX IF NOT EXISTS idx_etl_outbox_doc_id 
    ON etl_outbox (document_id);

CREATE INDEX IF NOT EXISTS idx_etl_outbox_created_at 
    ON etl_outbox (created_at);

-- 5. LangGraph PostgresSaver Standard Checkpoints Schema
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint BYTEA,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
