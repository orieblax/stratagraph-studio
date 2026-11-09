"""Structured output models for Pydantic AI micro-agents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RoutingDecision(BaseModel):
    """Structured decision output produced by the Supervisor Router Agent."""

    target_node: Literal[
        "etl_medallion_embedding_node",
        "hybrid_retriever_node",
        "mcp_tool_execution_node",
        "synthesis_output_guardrail_node",
        "end",
    ] = Field(
        description="Target LangGraph node selected for the next execution step."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.9,
        description="Confidence score for this routing decision (0.0 - 1.0).",
    )
    reasoning: str = Field(
        description="Technical justification and rationale explaining the selected route."
    )
    suggested_tool: str | None = Field(
        default=None,
        description="Name of the MCP tool to invoke if routing to mcp_tool_execution_node.",
    )
    tool_server: str | None = Field(
        default=None,
        description="Server namespace (e.g. postgres-local-mcp, supabase-cloud-mcp) if tool call.",
    )
    tool_arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured, validated arguments to be passed to the MCP tool.",
    )


class StructuredSynthesis(BaseModel):
    """High-fidelity structured synthesis produced by the Synthesis Agent."""

    summary: str = Field(
        description="Executive summary synthesizing the primary answer to the user query."
    )
    detailed_answer: str = Field(
        description="Comprehensive technical analysis citing evidence and reasoning."
    )
    key_findings: list[str] = Field(
        default_factory=list,
        description="Bulleted core takeaways or analytical findings extracted from context.",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Specific source chunk IDs or dataset references grounding the answer.",
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.95,
        description="Synthesis confidence score evaluating groundedness against context.",
    )
    suggested_next_steps: list[str] = Field(
        default_factory=list,
        description="Actionable follow-up questions, queries, or ETL actions for the operator.",
    )


class GuardrailEvaluation(BaseModel):
    """Security assessment output evaluated by the Input Guardrail Agent."""

    is_safe: bool = Field(
        description="Whether the query passes indirect injection and safety checks."
    )
    detected_risks: list[str] = Field(
        default_factory=list,
        description="List of detected risk categories (e.g., prompt injection, SSRF, PII).",
    )
    injection_detected: bool = Field(
        default=False,
        description="True if jailbreak, system prompt override, or boundary evasion was found.",
    )
    sanitized_query: str = Field(
        description="Sanitized version of user query with risks or sensitive elements scrubbed.",
    )
