"""Unit tests for TwoTierPgVectorCache, SmartModelTierRouter, and LoopAndCostCircuitBreaker."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.cost_optimization.infrastructure.circuit_breaker import LoopAndCostCircuitBreaker
from src.modules.cost_optimization.infrastructure.model_router import SmartModelTierRouter
from src.modules.cost_optimization.infrastructure.semantic_cache import (
    TwoTierPgVectorCache,
    compute_exact_hash,
)


def test_exact_hash_normalizes_whitespace_and_casing() -> None:
    p1 = "   What IS the REVENUE   for Q3?  "
    p2 = "what is the revenue for q3?"
    cfg = "cfg_hash_123"

    h1 = compute_exact_hash(p1, cfg)
    h2 = compute_exact_hash(p2, cfg)
    assert h1 == h2
    assert len(h1) == 64


def test_circuit_breaker_trips_on_loop_limit() -> None:
    cb = LoopAndCostCircuitBreaker()
    # Within bounds
    tripped, reason = cb.evaluate(loop_count=2, accumulated_cost_usd=0.45, max_iterations=3)
    assert tripped is False
    assert reason is None

    # Exceeds max iterations
    tripped, reason = cb.evaluate(loop_count=3, accumulated_cost_usd=0.45, max_iterations=3)
    assert tripped is True
    assert "Loop limit exceeded" in str(reason)


def test_circuit_breaker_trips_on_cost_boundary() -> None:
    cb = LoopAndCostCircuitBreaker()
    # Exceeds cost cap
    tripped, reason = cb.evaluate(loop_count=1, accumulated_cost_usd=1.55, max_cost_usd=1.50)
    assert tripped is True
    assert "Cost budget limit exceeded" in str(reason)


def test_smart_model_tier_router_decisions() -> None:
    router = SmartModelTierRouter()

    # Synthesis requires heavy model
    synthesis_dec = router.route_task("synthesis", preferred_provider="openai")
    assert synthesis_dec.provider == "openai"
    assert synthesis_dec.model_name == "gpt-4o"
    assert "flagship" in synthesis_dec.rationale.lower()

    # Guardrails route to lightweight model
    guardrail_dec = router.route_task("guardrail", preferred_provider="openai")
    assert guardrail_dec.model_name == "gpt-4o-mini"
    assert "lightweight" in guardrail_dec.rationale.lower()

    # Anthropic provider routing
    anthropic_dec = router.route_task("synthesis", preferred_provider="anthropic")
    assert anthropic_dec.model_name == "claude-3-5-sonnet"

    # Databricks routing
    databricks_dec = router.route_task("router", preferred_provider="databricks")
    assert "8b" in databricks_dec.model_name.lower() or "llama" in databricks_dec.model_name.lower()


def test_calculate_cost_computes_exact_micro_dollars() -> None:
    router = SmartModelTierRouter()
    # gpt-4o: $2.50 / 1M input, $10.00 / 1M output
    # 10,000 input tokens = $0.025, 2,000 output tokens = $0.020 -> Total = $0.045
    cost = router.calculate_cost("gpt-4o", input_tokens=10_000, output_tokens=2_000)
    assert cost == 0.045


@pytest.mark.asyncio
async def test_semantic_cache_tier1_hit_mock() -> None:
    # Setup mock session factory
    mock_session = AsyncMock()
    mock_result = MagicMock()
    # Return mock row for Tier 1: (id, response_text)
    mock_result.first.return_value = ("cache_uuid_1", "Cached answer for Tier 1.")
    mock_session.execute.return_value = mock_result

    session_maker = MagicMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    cache = TwoTierPgVectorCache(session_factory=session_maker)
    res = await cache.get(
        prompt="Tell me about project status",
        query_embedding=[0.0] * 1536,
        config_hash="cfg_abc",
    )

    assert res.hit is True
    assert res.tier == "exact"
    assert res.cached_response == "Cached answer for Tier 1."
    assert res.cost_usd == 0.0
