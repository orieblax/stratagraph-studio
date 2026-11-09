"""Integration tests for end-to-end LangGraph cyclic StateGraph execution."""

import pytest

from src.modules.orchestration.application.commands import (
    ExecuteWorkflowCommand,
    handle_execute_workflow,
)


@pytest.mark.asyncio
async def test_full_workflow_execution_cycle() -> None:
    cmd = ExecuteWorkflowCommand(
        user_query="How does Databricks Lakehouse Vector Search integrate with Delta tables?",
        thread_id="test_thread_001",
        provider="openai",
        model="gpt-4o",
        vector_backend="postgres_local",
        semantic_cache_enabled=False,  # Bypass cache to test full RAG + Rerank pipeline
        max_iterations=3,
        eval_sampling_rate=1.0,  # Ensure eval node runs
    )

    final_state = await handle_execute_workflow(cmd)

    # 1. State assertions
    assert final_state is not None
    assert final_state["user_query"] == cmd.user_query
    assert final_state["loop_count"] >= 1
    assert final_state["circuit_breaker_tripped"] is False

    # 2. RAG & Re-Ranking
    assert len(final_state["retrieved_chunks"]) > 0
    assert len(final_state["reranked_chunks"]) > 0
    # Chunks are wrapped in cryptographic spotlighting tags
    assert "<untrusted_context_" in final_state["retrieved_chunks"][0]["content"]

    # 3. Output Synthesis
    assert len(final_state["synthesized_output"]) > 0
    assert final_state["accumulated_cost_usd"] > 0.0

    # 4. Async LangSmith Evaluation
    eval_scores = final_state["eval_scores"]
    assert "context_relevance" in eval_scores
    assert "groundedness" in eval_scores
    assert "answer_relevance" in eval_scores
    assert eval_scores["trajectory_score"] > 0.5


@pytest.mark.asyncio
async def test_cache_hit_short_circuits_workflow() -> None:
    # First execution to populate cache
    thread_1 = "thread_cache_populate"
    cmd_1 = ExecuteWorkflowCommand(
        user_query="Explain ACID transactions in Lakehouse Delta Lake.",
        thread_id=thread_1,
        semantic_cache_enabled=True,
    )
    state_1 = await handle_execute_workflow(cmd_1)
    assert state_1["synthesized_output"] != ""

    # Second execution with identical prompt to verify Tier-1 exact cache hit
    thread_2 = "thread_cache_hit"
    cmd_2 = ExecuteWorkflowCommand(
        user_query="Explain ACID transactions in Lakehouse Delta Lake.",
        thread_id=thread_2,
        semantic_cache_enabled=True,
    )
    state_2 = await handle_execute_workflow(cmd_2)

    assert state_2["cache_hit"] is True
    assert state_2["cache_tier"] in ("exact", "semantic")
    assert state_2["synthesized_output"] == state_1["synthesized_output"]
