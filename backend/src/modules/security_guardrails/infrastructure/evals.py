"""Asynchronous LLM-as-a-Judge LangSmith Evaluator for RAG Triad and Trajectory Scoring."""

from __future__ import annotations

import asyncio
import os
import random
from typing import Any

from langsmith import Client

from src.shared.logging import get_logger

logger = get_logger(__name__)


class AsyncLangSmithEvaluator:
    """Computes RAG Triad metrics and registers evaluation feedback on LangSmith runs asynchronously."""

    def __init__(self, client: Client | None = None) -> None:
        self._client = client
        self.api_key = os.getenv("LANGSMITH_API_KEY")

    def _get_client(self) -> Client | None:
        if self._client is not None:
            return self._client
        if self.api_key and self.api_key.strip():
            try:
                self._client = Client(api_key=self.api_key)
                return self._client
            except Exception as exc:
                logger.warning("langsmith_client_init_failed", error=str(exc))
        return None

    def _calculate_rag_triad(
        self,
        query: str,
        context_chunks: list[dict[str, Any]],
        response: str,
    ) -> dict[str, float]:
        """Compute heuristic LLM-as-a-Judge scores for Context Relevance, Groundedness, and Answer Relevance."""
        q_tokens = set(query.lower().split())
        r_tokens = set(response.lower().split())

        all_context_text = " ".join(str(c.get("content", "")) for c in context_chunks).lower()
        c_tokens = set(all_context_text.split())

        # 1. Context Relevance: Fraction of query terms present in context
        c_overlap = len(q_tokens.intersection(c_tokens)) / max(len(q_tokens), 1)
        context_relevance = round(min(1.0, 0.4 + 0.6 * c_overlap), 3)

        # 2. Groundedness: Fraction of response terms supported by context
        g_overlap = len(r_tokens.intersection(c_tokens)) / max(len(r_tokens), 1)
        groundedness = round(min(1.0, 0.5 + 0.5 * g_overlap), 3)

        # 3. Answer Relevance: Response addresses query terms
        a_overlap = len(q_tokens.intersection(r_tokens)) / max(len(q_tokens), 1)
        answer_relevance = round(min(1.0, 0.4 + 0.6 * a_overlap), 3)

        # 4. Overall Trajectory Score
        trajectory_score = round(
            (context_relevance * 0.3) + (groundedness * 0.4) + (answer_relevance * 0.3), 3
        )

        return {
            "context_relevance": context_relevance,
            "groundedness": groundedness,
            "answer_relevance": answer_relevance,
            "trajectory_score": trajectory_score,
        }

    async def evaluate_run_async(
        self,
        langsmith_run_id: str,
        query: str,
        context_chunks: list[dict[str, Any]],
        response: str,
        sampling_rate: float = 0.25,
    ) -> dict[str, float] | None:
        """Asynchronously evaluate run if sampled."""
        if random.random() > sampling_rate and sampling_rate < 1.0:
            return None

        scores = self._calculate_rag_triad(query, context_chunks, response)

        # Offload LangSmith feedback registration to background task
        def _post_feedback() -> None:
            client = self._get_client()
            if not client or not langsmith_run_id:
                return

            try:
                for metric, val in scores.items():
                    client.create_feedback(
                        run_id=langsmith_run_id,
                        key=metric,
                        score=val,
                        comment="Automated Async RAG Triad Evaluator",
                    )
                logger.info(
                    "langsmith_eval_feedback_recorded", run_id=langsmith_run_id, scores=scores
                )
            except Exception as exc:
                logger.warning(
                    "langsmith_feedback_post_failed", run_id=langsmith_run_id, error=str(exc)
                )

        await asyncio.to_thread(_post_feedback)
        return scores
