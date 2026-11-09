"""StrataGraph Studio Backend - FastAPI Modular Monolith Entry Point."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.modules.cost_optimization.presentation.router import router as cost_router
from src.modules.mcp_hub.presentation.router import router as mcp_router
from src.modules.orchestration.presentation.router import router as orchestration_router
from src.modules.rag_etl.presentation.router import router as rag_router
from src.modules.security_guardrails.presentation.middleware import security_headers_middleware
from src.modules.security_guardrails.presentation.router import router as security_router
from src.shared.logging import configure_logging, get_logger

# Configure structured logging with automatic PII / Secret redaction
log_level = os.getenv("LOG_LEVEL", "INFO")
json_logs = os.getenv("ENVIRONMENT", "development") != "development"
configure_logging(level=log_level, json_output=json_logs)
logger = get_logger("stratagraph.main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing DB connection pool and background services."""
    logger.info("stratagraph_studio_starting", env=os.getenv("ENVIRONMENT", "development"))
    yield
    logger.info("stratagraph_studio_shutdown")


app = FastAPI(
    title="StrataGraph Studio API",
    description="Visual Agentic Orchestration, Medallion RAG & MCP Control Plane",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# 1. Defense-in-Depth Security Headers Middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=security_headers_middleware)

# 2. CORS Middleware with explicit allowable origins
cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
allow_origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "Content-Disposition"],
)

# 3. Mount Bounded Context Domain Routers under /api/v1
app.include_router(orchestration_router, prefix="/api/v1")
app.include_router(rag_router, prefix="/api/v1")
app.include_router(cost_router, prefix="/api/v1")
app.include_router(mcp_router, prefix="/api/v1")
app.include_router(security_router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["Health"])
async def root_health_check() -> dict[str, str]:
    """Root healthcheck endpoint for Docker container health check."""
    return {"status": "HEALTHY", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")  # nosec B104
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.main:app", host=host, port=port, reload=True)
