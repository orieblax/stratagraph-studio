"""Loop and Cost Circuit Breaker to prevent runaway LLM agent loops and budget overruns."""

from __future__ import annotations

from src.modules.cost_optimization.domain.interfaces import ICircuitBreaker
from src.shared.logging import get_logger

logger = get_logger(__name__)


class LoopAndCostCircuitBreaker(ICircuitBreaker):
    """Enforces execution iteration limits and cumulative USD micro-cost budget boundaries."""

    def evaluate(
        self,
        loop_count: int,
        accumulated_cost_usd: float,
        *,
        max_iterations: int = 3,
        max_cost_usd: float = 1.50,
    ) -> tuple[bool, str | None]:
        """Check if execution thresholds have been exceeded."""
        if loop_count >= max_iterations:
            reason = (
                f"Loop limit exceeded: agent reached {loop_count} iterations (maximum allowable: {max_iterations}). "
                "Circuit breaker tripped to prevent infinite cyclic loop."
            )
            logger.warning(
                "circuit_breaker_tripped_loop_limit",
                loop_count=loop_count,
                max_iterations=max_iterations,
            )
            return True, reason

        if accumulated_cost_usd >= max_cost_usd:
            reason = (
                f"Cost budget limit exceeded: accumulated USD ${accumulated_cost_usd:.4f} "
                f"(maximum allowable: ${max_cost_usd:.4f}). "
                "Circuit breaker tripped to prevent budget exhaustion."
            )
            logger.warning(
                "circuit_breaker_tripped_cost_limit",
                accumulated_cost_usd=accumulated_cost_usd,
                max_cost_usd=max_cost_usd,
            )
            return True, reason

        return False, None
