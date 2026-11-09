"""FastAPI router for hardened document ingestion and transactional ETL outbox."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from src.modules.cost_optimization.infrastructure.model_router import OpenAIProvider
from src.modules.rag_etl.infrastructure.chunker_outbox import IdempotentOutboxChunker
from src.modules.security_guardrails.infrastructure.file_ssrf_validator import FileSecurityValidator
from src.modules.security_guardrails.presentation.middleware import (
    authenticate_request,
    extract_ephemeral_secrets_dependency,
)
from src.shared.registry import get_vector_store

router = APIRouter(prefix="/rag-etl", tags=["RAG & ETL Ingestion"])
_file_validator = FileSecurityValidator()
_embedder = OpenAIProvider()


class IngestTextRequest(BaseModel):
    document_id: str = Field(..., description="Unique document ID")
    raw_text: str = Field(..., description="Document content text")
    vector_backend: str = Field(default="postgres_local")
    chunk_size: int = Field(default=500)
    chunk_overlap: int = Field(default=50)


@router.post("/upload", dependencies=[Depends(extract_ephemeral_secrets_dependency)])
async def upload_document_endpoint(
    file: UploadFile = File(...),
    vector_backend: str = Form("postgres_local"),
    _user: dict[str, Any] = Depends(authenticate_request),
) -> dict[str, Any]:
    """Upload and validate document into quarantined safe storage."""
    safe_dir = os.getenv("SAFE_UPLOAD_DIR", str(Path(tempfile.gettempdir()) / "safe_uploads"))
    file_bytes = await file.read()

    filename = file.filename or "uploaded_file.txt"
    val_res = _file_validator.validate_file(file_bytes, filename, destination_dir=safe_dir)

    async with aiofiles.open(val_res.canonical_path, "wb") as f:
        await f.write(file_bytes)

    # Initialize Outbox
    doc_id = Path(val_res.canonical_path).stem
    repo_cls = get_vector_store(vector_backend)
    repo = repo_cls()
    chunker = IdempotentOutboxChunker(vector_repo=repo, embedding_provider=_embedder)

    outbox_id = await chunker.initialize_outbox_record(
        document_id=doc_id,
        file_name=filename,
        file_path=val_res.canonical_path,
    )

    return {
        "status": "STAGED",
        "document_id": doc_id,
        "outbox_id": outbox_id,
        "mime_type": val_res.mime_type,
        "byte_size": val_res.byte_size,
        "canonical_path": val_res.canonical_path,
    }


@router.post("/ingest", dependencies=[Depends(extract_ephemeral_secrets_dependency)])
async def ingest_text_endpoint(
    req: IngestTextRequest,
    _user: dict[str, Any] = Depends(authenticate_request),
) -> dict[str, Any]:
    """Ingest, chunk, embed, and upsert document text."""
    repo_cls = get_vector_store(req.vector_backend)
    repo = repo_cls()
    chunker = IdempotentOutboxChunker(vector_repo=repo, embedding_provider=_embedder)

    outbox_id = await chunker.initialize_outbox_record(
        document_id=req.document_id,
        file_name=f"{req.document_id}.txt",
        file_path=f"/safe_uploads/{req.document_id}.txt",
    )

    try:
        inserted_ids = await chunker.process_document_etl(
            outbox_id=outbox_id,
            document_id=req.document_id,
            raw_text=req.raw_text,
            chunk_size=req.chunk_size,
            chunk_overlap=req.chunk_overlap,
        )
        return {
            "status": "SUCCESS",
            "document_id": req.document_id,
            "outbox_id": outbox_id,
            "chunks_indexed": len(inserted_ids),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ETL Ingestion failed: {exc}",
        ) from exc
