"""Security middleware: JWT Bearer validation, token-bucket rate limiting, and ephemeral header extraction."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import jwt
from fastapi import Header, HTTPException, Request, Response, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.shared.ephemeral_secrets import EphemeralSecretVault
from src.shared.logging import correlation_id_ctx, get_logger

logger = get_logger(__name__)

JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "insecure_dev_jwt_secret_change_in_production_min32chars"
)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

security_bearer = HTTPBearer(auto_error=False)


# ==============================================================================
# Token-Bucket Rate Limiter
# ==============================================================================


class TokenBucketRateLimiter:
    """In-memory thread-safe token-bucket rate limiter per client/user."""

    def __init__(self, rate_per_minute: int = 120) -> None:
        self.capacity = float(rate_per_minute)
        self.fill_rate = self.capacity / 60.0  # tokens per second
        self.buckets: dict[str, dict[str, float]] = {}

    def is_allowed(self, client_id: str) -> bool:
        """Check if client has tokens available; deduct 1 token if allowed."""
        now = time.time()
        bucket = self.buckets.get(client_id)

        if bucket is None:
            self.buckets[client_id] = {"tokens": self.capacity - 1.0, "last_update": now}
            return True

        tokens = bucket["tokens"]
        last_update = bucket["last_update"]
        elapsed = now - last_update

        # Refill tokens
        refilled = min(self.capacity, tokens + (elapsed * self.fill_rate))

        if refilled >= 1.0:
            self.buckets[client_id] = {"tokens": refilled - 1.0, "last_update": now}
            return True
        else:
            self.buckets[client_id]["tokens"] = refilled
            self.buckets[client_id]["last_update"] = now
            return False


rate_limiter = TokenBucketRateLimiter(
    rate_per_minute=int(os.getenv("RATE_LIMIT_TOKENS_PER_MINUTE", "120"))
)


# ==============================================================================
# JWT Authentication & Ephemeral Secret Extraction
# ==============================================================================


def create_studio_jwt_token(
    user_id: str = "studio_developer", expires_in_minutes: int = 1440
) -> str:
    """Issue a signed JWT Bearer token for local studio or user sessions."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + (expires_in_minutes * 60),
        "role": "studio_admin",
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict[str, Any]:
    """Verify and decode a JWT Bearer token."""
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc


async def authenticate_request(
    request: Request,
    auth_credentials: HTTPAuthorizationCredentials | None = Security(security_bearer),
) -> dict[str, Any]:
    """FastAPI dependency verifying Bearer token and enforcing rate limits."""
    # 1. Rate Limiting Check
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before submitting more requests.",
        )

    # 2. Extract Bearer token from header or query param (for EventSource SSE)
    token: str | None = None
    if auth_credentials:
        token = auth_credentials.credentials
    elif "token" in request.query_params:
        token = request.query_params["token"]

    if not token:
        # In development mode, auto-issue session if authorization is missing
        env = os.getenv("ENVIRONMENT", "development")
        if env == "development":
            token = create_studio_jwt_token(user_id="dev_user")
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization Bearer token header.",
            )

    return verify_jwt_token(token)


async def extract_ephemeral_secrets_dependency(
    x_databricks_token: str | None = Header(None, alias="X-Databricks-Token"),
    x_supabase_key: str | None = Header(None, alias="X-Supabase-Key"),
    x_openai_key: str | None = Header(None, alias="X-OpenAI-Key"),
    x_anthropic_key: str | None = Header(None, alias="X-Anthropic-Key"),
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
) -> None:
    """Inject UI ConfigPanel ephemeral tokens and correlation tracking into request context."""
    secrets_map: dict[str, str | None] = {
        "DATABRICKS_TOKEN": x_databricks_token,
        "SUPABASE_SERVICE_KEY": x_supabase_key,
        "OPENAI_API_KEY": x_openai_key,
        "ANTHROPIC_API_KEY": x_anthropic_key,
    }
    EphemeralSecretVault.set_secrets(secrets_map)

    if x_correlation_id:
        correlation_id_ctx.set(x_correlation_id)


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Any]
) -> Response:
    """Middleware enforcing defense-in-depth HTTP security headers."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
