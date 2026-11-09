"""Domain interfaces for cost optimization, semantic cache, and FinOps guardrails."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class CacheResult:
    """Result of querying the Two-Tier semantic cache."""

    hit: bool
    tier: str | None = None  # "exact", "semantic", or None
    cached_response: str | None = None
    similarity_score: float = 0.0
    latency_ms: float = 0.0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class RouterDecision:
    """Decision made by the smart model tiering router."""

    task_tier: str  # "guardrail", "router", "query_rewrite", "synthesis"
    provider: str  # "openai", "anthropic", "ollama", "databricks"
    model_name: str
    estimated_input_cost_per_1k: float
    estimated_output_cost_per_1k: float
    rationale: str


@dataclass(frozen=True)
class FinOpsCostBreakdown:
    """Detailed micro-cost and token metrics for a single node or workflow execution."""

    node_name: str
    provider: str
    model_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    cached: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ISemanticCache(Protocol):
    """Protocol for two-tier exact and pgvector semantic caching."""

    async def get(
        self,
        prompt: str,
        query_embedding: list[float],
        config_hash: str,
        *,
        threshold: float = 0.92,
    ) -> CacheResult:
        """Query Tier-1 exact hash and Tier-2 pgvector cosine similarity."""
        ...

    async def set(
        self,
        prompt: str,
        response: str,
        embedding: list[float],
        config_hash: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist a response into the exact and semantic cache."""
        ...

    async def flush(self, config_hash: str | None = None) -> int:
        """Flush cache entries."""
        ...


class IModelRouter(Protocol):
    """Protocol for tier-based intelligent LLM routing."""

    def route_task(
        self,
        task_tier: str,
        *,
        preferred_provider: str | None = None,
        max_cost_preference: float | None = None,
    ) -> RouterDecision:
        """Route an agentic task to the optimal model based on tier and cost constraints."""
        ...

    def calculate_cost(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate micro-USD cost based on provider pricing tables."""
        ...


class ICircuitBreaker(Protocol):
    """Protocol for enforcing execution loop and USD cost thresholds."""

    def evaluate(
        self,
        loop_count: int,
        accumulated_cost_usd: float,
        *,
        max_iterations: int = 3,
        max_cost_usd: float = 1.50,
    ) -> tuple[bool, str | None]:
        """Check if workflow should trip circuit breaker and route to fallback."""
        ...
