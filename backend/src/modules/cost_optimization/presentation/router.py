"""FastAPI router for FinOps pricing, cache statistics, and cache flushing."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.modules.cost_optimization.infrastructure.model_router import MODEL_PRICING
from src.modules.cost_optimization.infrastructure.semantic_cache import TwoTierPgVectorCache
from src.modules.security_guardrails.presentation.middleware import authenticate_request

router = APIRouter(prefix="/cost-optimization", tags=["Cost & FinOps"])
_cache = TwoTierPgVectorCache()


class FlushCacheRequest(BaseModel):
    config_hash: str | None = Field(default=None, description="Optional config hash filter")


@router.get("/pricing")
async def get_pricing_table_endpoint(
    _user: dict[str, Any] = Depends(authenticate_request),
) -> dict[str, Any]:
    """Retrieve model pricing table for token budgeting and FinOps metrics."""
    return {
        "pricing_per_million_tokens": {
            model: {"input_usd": rates[0], "output_usd": rates[1]}
            for model, rates in MODEL_PRICING.items()
        }
    }


@router.post("/cache/flush")
async def flush_cache_endpoint(
    req: FlushCacheRequest,
    _user: dict[str, Any] = Depends(authenticate_request),
) -> dict[str, Any]:
    """Flush entries from the Two-Tier semantic cache."""
    cleared = await _cache.flush(req.config_hash)
    return {
        "status": "FLUSHED",
        "entries_deleted": cleared,
        "config_hash": req.config_hash,
    }
