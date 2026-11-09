"""Node 3: Supervisor Router Node (Intent classification, loop/cost check, dynamic routing)."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.modules.cost_optimization.infrastructure.circuit_breaker import LoopAndCostCircuitBreaker
from src.modules.cost_optimization.infrastructure.model_router import SmartModelTierRouter
from src.modules.orchestration.domain.interfaces import TopologyEvent
from src.modules.orchestration.domain.state import AgentState
from src.modules.orchestration.infrastructure.pydantic_ai.agents import create_router_agent
from src.modules.orchestration.infrastructure.pydantic_ai.deps import RouterDeps
from src.shared.registry import register_node

NODE_NAME = "supervisor_router_node"
_circuit_breaker = LoopAndCostCircuitBreaker()
_router = SmartModelTierRouter()


@register_node(NODE_NAME)
async def supervisor_router_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Evaluate loop/cost circuit breakers and dynamically select the next visual execution path."""
    start_time = time.time()
    streamer = config.get("configurable", {}).get("streamer") if config else None
    cid = state.get("correlation_id", "")

    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_start",
                node_id=NODE_NAME,
                status="Running",
                correlation_id=cid,
            )
        )

    loop_cnt = state.get("loop_count", 0) + 1
    acc_cost = state.get("accumulated_cost_usd", 0.0)
    max_iters = config.get("configurable", {}).get("max_iterations", 3) if config else 3
    max_cost = config.get("configurable", {}).get("max_cost_usd", 1.50) if config else 1.50

    # 1. Circuit Breaker Check
    tripped, reason = _circuit_breaker.evaluate(
        loop_cnt,
        acc_cost,
        max_iterations=max_iters,
        max_cost_usd=max_cost,
    )

    if tripped:
        exec_ms = round((time.time() - start_time) * 1000, 2)
        if streamer:
            await streamer.emit_topology(
                TopologyEvent(
                    event_type="node_end",
                    node_id=NODE_NAME,
                    status="Blocked by Guardrail",
                    execution_time_ms=exec_ms,
                    correlation_id=cid,
                    details={"circuit_breaker_tripped": True, "reason": reason},
                )
            )
        return {
            "loop_count": loop_cnt,
            "circuit_breaker_tripped": True,
            "circuit_breaker_reason": reason,
            "synthesized_output": f"Workflow halted by FinOps Circuit Breaker: {reason}",
            "active_route": "synthesis_output_guardrail_node",
        }

    # 2. Pydantic AI Structured Router Evaluation
    pref_provider = (config.get("configurable", {}).get("provider") if config else None) or "openai"
    router_agent = create_router_agent(provider=pref_provider)
    router_deps = RouterDeps(
        user_query=state.get("user_query", ""),
        loop_count=loop_cnt,
        accumulated_cost_usd=acc_cost,
        max_iterations=max_iters,
        max_cost_usd=max_cost,
        has_mcp_scratchpad=bool(state.get("mcp_scratchpad")),
        selected_vector_backend=state.get("selected_vector_backend", "postgres_local"),
    )

    pydantic_decision: dict[str, Any] | None = None
    try:
        agent_res = await router_agent.run(state.get("user_query", ""), deps=router_deps)
        pydantic_decision = agent_res.output.model_dump()
    except Exception:
        pydantic_decision = None

    # 3. Intent Classification and Dynamic Routing
    query = state.get("user_query", "").lower()
    hitl_pending: dict[str, Any] | None = None

    # Route 0: Post-Tool Synthesis (if tool has already run)
    if state.get("mcp_scratchpad"):
        selected_route = "synthesis_output_guardrail_node"

    # Route 1: Direct File Ingestion / Medallion ETL
    elif any(k in query for k in ("ingest", "chunk", "etl", "volume", "medallion", "upload")):
        selected_route = "etl_medallion_embedding_node"

    # Route 2: MCP Tool Action (explicit tool requests or side-effects)
    elif any(
        k in query
        for k in ("send email", "create task", "query lakehouse", "sql write", "insert into")
    ):
        selected_route = "mcp_tool_execution_node"
        if "send email" in query:
            s_name, t_name = "workspace-ops-mcp", "send_email"
            args = {
                "recipient": "ops-lead@enterprise.org",
                "subject": "Automated Notification",
                "body": state.get("user_query", ""),
            }
        elif "create task" in query:
            s_name, t_name = "supabase-cloud-mcp", "create_task"
            args = {
                "title": "Automated System Task",
                "priority": "high",
                "description": state.get("user_query", ""),
            }
        elif "query lakehouse" in query:
            s_name, t_name = "databricks-lakehouse-mcp", "query_lakehouse_sql"
            args = {"query": "SELECT * FROM bronze_documents LIMIT 5"}
        elif "sql write" in query or "insert into" in query:
            s_name, t_name = "postgres-local-mcp", "execute_local_write_query"
            args = {
                "query": "INSERT INTO etl_outbox (document_id, file_name, file_path) VALUES ('doc_test', 'test.txt', '/safe/test.txt')"
            }
        else:
            s_name, t_name = "postgres-local-mcp", "inspect_local_schema"
            args = {}

        hitl_pending = {
            "server_name": s_name,
            "tool_name": t_name,
            "arguments": args,
            "reason": "Operator verification required before executing tool.",
        }

    # Route 3: Hybrid Retrieval (if chunks not yet gathered)
    elif not state.get("reranked_chunks") and not state.get("retrieved_chunks"):
        selected_route = "hybrid_retriever_node"

    # Route 4: Final Synthesis
    else:
        selected_route = "synthesis_output_guardrail_node"

    exec_ms = round((time.time() - start_time) * 1000, 2)
    if streamer:
        await streamer.emit_topology(
            TopologyEvent(
                event_type="node_end",
                node_id=NODE_NAME,
                status="Success",
                execution_time_ms=exec_ms,
                correlation_id=cid,
                details={"selected_route": selected_route, "loop_count": loop_cnt},
            )
        )

    ret_state: dict[str, Any] = {
        "loop_count": loop_cnt,
        "circuit_breaker_tripped": False,
        "circuit_breaker_reason": None,
        "active_route": selected_route,
        "routing_decision": pydantic_decision,
    }
    if hitl_pending:
        ret_state["hitl_pending_action"] = hitl_pending
    return ret_state
