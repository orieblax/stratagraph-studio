"""LangGraph cyclic StateGraph compilation, checkpointing, and execution orchestrator."""

from __future__ import annotations

import uuid
from typing import Any, cast

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.modules.orchestration.domain.interfaces import (
    IWorkflowOrchestrator,
    WorkflowExecutionConfig,
)
from src.modules.orchestration.domain.state import AgentState
from src.modules.orchestration.infrastructure.nodes import (
    async_langsmith_eval_node,
    etl_medallion_embedding_node,
    hybrid_retriever_node,
    input_guardrail_node,
    mcp_tool_execution_node,
    reranker_node,
    semantic_cache_memory_node,
    supervisor_router_node,
    synthesis_output_guardrail_node,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


def build_agent_graph(checkpointer: Any = None) -> Any:
    """Construct the 9-node cyclic LangGraph StateGraph with conditional routing."""
    builder = StateGraph(AgentState)

    # 1. Add all 9 visualizable nodes
    builder.add_node("input_guardrail_node", input_guardrail_node)
    builder.add_node("semantic_cache_memory_node", semantic_cache_memory_node)
    builder.add_node("supervisor_router_node", supervisor_router_node)
    builder.add_node("etl_medallion_embedding_node", etl_medallion_embedding_node)
    builder.add_node("hybrid_retriever_node", hybrid_retriever_node)
    builder.add_node("reranker_node", reranker_node)
    builder.add_node("mcp_tool_execution_node", mcp_tool_execution_node)
    builder.add_node("synthesis_output_guardrail_node", synthesis_output_guardrail_node)
    builder.add_node("async_langsmith_eval_node", async_langsmith_eval_node)

    # 2. Add linear entry flow
    builder.add_edge(START, "input_guardrail_node")
    builder.add_edge("input_guardrail_node", "semantic_cache_memory_node")

    # 3. Conditional Branch from Semantic Cache
    def _route_cache(state: AgentState) -> str:
        if state.get("cache_hit"):
            return "synthesis_output_guardrail_node"
        return "supervisor_router_node"

    builder.add_conditional_edges(
        "semantic_cache_memory_node",
        _route_cache,
        {
            "synthesis_output_guardrail_node": "synthesis_output_guardrail_node",
            "supervisor_router_node": "supervisor_router_node",
        },
    )

    # 4. Dynamic Branching from Supervisor Router
    def _route_supervisor(state: AgentState) -> str:
        return state.get("active_route", "synthesis_output_guardrail_node")

    builder.add_conditional_edges(
        "supervisor_router_node",
        _route_supervisor,
        {
            "etl_medallion_embedding_node": "etl_medallion_embedding_node",
            "hybrid_retriever_node": "hybrid_retriever_node",
            "mcp_tool_execution_node": "mcp_tool_execution_node",
            "synthesis_output_guardrail_node": "synthesis_output_guardrail_node",
        },
    )

    # 5. Cyclic Loopback Edges
    builder.add_edge("etl_medallion_embedding_node", "supervisor_router_node")
    builder.add_edge("hybrid_retriever_node", "reranker_node")
    builder.add_edge("reranker_node", "supervisor_router_node")
    builder.add_edge("mcp_tool_execution_node", "supervisor_router_node")

    # 6. Exit Flow
    builder.add_edge("synthesis_output_guardrail_node", "async_langsmith_eval_node")
    builder.add_edge("async_langsmith_eval_node", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(
        checkpointer=saver,
        interrupt_before=["mcp_tool_execution_node"],
    )


class LangGraphWorkflowOrchestrator(IWorkflowOrchestrator):
    """Production orchestrator managing cyclic execution, HITL gates, and time-travel forks."""

    def __init__(self, checkpointer: Any = None) -> None:
        self.checkpointer = checkpointer or MemorySaver()
        self.graph = build_agent_graph(checkpointer=self.checkpointer)

    async def run_workflow(
        self,
        user_query: str,
        config: WorkflowExecutionConfig,
        initial_state: dict[str, Any] | None = None,
        streamer: Any = None,
    ) -> AgentState:
        """Run workflow from start or checkpoint."""
        cid = str(uuid.uuid4())
        run_config = {
            "configurable": {
                "thread_id": config.thread_id,
                "provider": config.provider,
                "model": config.model,
                "temperature": config.temperature,
                "vector_backend": config.vector_backend,
                "semantic_cache_enabled": config.semantic_cache_enabled,
                "semantic_cache_threshold": config.semantic_cache_threshold,
                "max_iterations": config.max_iterations,
                "max_cost_usd": config.max_cost_usd,
                "reranker_device_policy": config.reranker_device_policy,
                "eval_sampling_rate": config.eval_sampling_rate,
                "manual_hitl_tools": config.manual_hitl_tools,
                "streamer": streamer,
            }
        }

        base_state: AgentState = {
            "messages": [{"role": "user", "content": user_query}],
            "user_query": user_query,
            "correlation_id": cid,
            "langsmith_run_id": f"ls_run_{cid[:8]}",
            "config_hash": f"cfg_{config.provider}_{config.vector_backend}",
            "selected_vector_backend": config.vector_backend,
            "tainted_context": False,
            "spotlight_nonces": [],
            "hitl_pending_action": None,
            "hitl_approved": None,
            "loop_count": 0,
            "total_tokens": 0,
            "accumulated_cost_usd": 0.0,
            "circuit_breaker_tripped": False,
            "cache_hit": False,
            "retrieved_chunks": [],
            "reranked_chunks": [],
            "mcp_scratchpad": [],
            "sql_audit_log": [],
            "medallion_status": {},
            "eval_scores": {},
            "synthesized_output": "",
        }

        if initial_state:
            cast(dict[str, Any], base_state).update(initial_state)

        # Execute async invocation
        final_state: AgentState = await self.graph.ainvoke(base_state, config=run_config)
        return final_state

    async def resume_workflow(
        self,
        thread_id: str,
        approved: bool,
        modification: dict[str, Any] | None = None,
        streamer: Any = None,
    ) -> AgentState:
        """Resume execution following an HITL gate."""
        run_config = {
            "configurable": {
                "thread_id": thread_id,
                "streamer": streamer,
            }
        }

        # Update state with decision
        update_state: dict[str, Any] = {
            "hitl_approved": approved,
        }
        if modification:
            update_state.update(modification)

        await self.graph.aupdate_state(run_config, update_state)
        # Continue execution
        resumed_state: AgentState = await self.graph.ainvoke(None, config=run_config)
        return resumed_state

    def get_checkpoint_history(self, thread_id: str) -> list[dict[str, Any]]:
        """Retrieve historical checkpoints for time-travel visual inspection."""
        run_config = {"configurable": {"thread_id": thread_id}}
        history: list[dict[str, Any]] = []
        try:
            for state_snapshot in self.graph.get_state_history(run_config):
                history.append(
                    {
                        "checkpoint_id": state_snapshot.config.get("configurable", {}).get(
                            "checkpoint_id", ""
                        ),
                        "next_nodes": state_snapshot.next,
                        "created_at": state_snapshot.created_at,
                        "values": state_snapshot.values,
                    }
                )
        except Exception:
            pass
        return history
