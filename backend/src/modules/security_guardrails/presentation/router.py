"""FastAPI router for security diagnostics, session token issuance, and SQL AST verification."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.modules.security_guardrails.infrastructure.sql_validator import SQLSecurityValidator
from src.modules.security_guardrails.presentation.middleware import create_studio_jwt_token

router = APIRouter(prefix="/security", tags=["Security & Auth"])
_sql_validator = SQLSecurityValidator()


class ValidateSQLRequest(BaseModel):
    query: str = Field(..., description="SQL string to analyze")
    dialect: str = Field(default="postgres")
    read_only: bool = Field(default=True)
    max_limit: int = Field(default=100)


@router.get("/health")
async def health_check_endpoint() -> dict[str, Any]:
    """Basic health check and system status."""
    return {
        "status": "HEALTHY",
        "service": "StrataGraph Studio Control Plane",
        "version": "0.1.0",
    }


@router.get("/auth/studio-session")
async def get_studio_session_token(user_id: str = "studio_developer") -> dict[str, str]:
    """Issue a signed JWT Bearer token for local development session."""
    token = create_studio_jwt_token(user_id=user_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user_id,
    }


@router.post("/validate-sql")
async def validate_sql_endpoint(req: ValidateSQLRequest) -> dict[str, Any]:
    """Validate query against SQL AST security rules without executing."""
    try:
        val_res = _sql_validator.validate_and_rewrite(
            req.query,
            dialect=req.dialect,
            read_only=req.read_only,
            max_limit=req.max_limit,
        )
        return {
            "is_valid": val_res.is_valid,
            "sanitized_sql": val_res.sanitized_sql,
            "ast_type": val_res.ast_type,
            "tables_accessed": val_res.tables_accessed,
            "has_mutations": val_res.has_mutations,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
