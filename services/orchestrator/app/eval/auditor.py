"""Asynchronous audit plane: Judge LLM scores ExtractionBundle and answer vs ground truth."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.rag.schemas import ExtractionBundle

try:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
    _JUDGE_AVAILABLE = True
except ImportError:
    _JUDGE_AVAILABLE = False


class AuditScores(BaseModel):
    """Structured output from Judge LLM."""

    faithfulness: float = Field(
        ge=0.0,
        le=1.0,
        description="Citation/source accuracy of the extraction (0-1).",
    )
    answer_correctness: float = Field(
        ge=0.0,
        le=1.0,
        description="Correctness of the final answer vs ground truth (0-1).",
    )


audit_scores_schema = AuditScores


def _get_judge_llm():
    """Prefer Claude then GPT-4o for Judge."""
    if not _JUDGE_AVAILABLE:
        return None
    if os.getenv("ANTHROPIC_API_KEY"):
        return ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            temperature=0,
        ).with_structured_output(AuditScores)
    if os.getenv("OPENAI_API_KEY"):
        return ChatOpenAI(
            model="gpt-4o",
            temperature=0,
        ).with_structured_output(AuditScores)
    return None


@dataclass
class AuditResult:
    trace_id: str
    faithfulness: float
    answer_correctness: float
    has_ground_truth: bool


class AuditPlane:
    """Loads extraction + trajectory for a trace and runs Judge LLM to score."""

    def __init__(
        self,
        get_extraction: Any,
        get_trajectory_steps: Any,
    ) -> None:
        self.get_extraction = get_extraction
        self.get_trajectory_steps = get_trajectory_steps

    async def audit(
        self,
        trace_id: str,
        ground_truth: str | None = None,
    ) -> AuditResult | None:
        bundle, final_answer = await self.get_extraction(trace_id)
        if bundle is None:
            return None
        steps = await self.get_trajectory_steps(trace_id)
        judge = _get_judge_llm()
        if judge is None:
            return AuditResult(
                trace_id=trace_id,
                faithfulness=0.0,
                answer_correctness=0.0,
                has_ground_truth=ground_truth is not None,
            )
        claims_text = [c.text for c in bundle.claims]
        context = (
            f"Query: {bundle.query}\n"
            f"Extracted claims: {claims_text}\n"
            f"Final answer: {final_answer or '(none)'}\n"
        )
        if ground_truth:
            context += f"Ground truth: {ground_truth}\n"
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a Judge. Score the extraction pipeline output.\n"
                    "Faithfulness: 0-1, how well do citations/sources support the claims?\n"
                    "Answer Correctness: 0-1, how correct is the final answer compared to ground truth (if provided)? "
                    "If no ground truth, use 0.5 as neutral.",
                ),
                ("human", "{context}"),
            ]
        )
        chain = prompt | judge
        result = await chain.ainvoke({"context": context})
        return AuditResult(
            trace_id=trace_id,
            faithfulness=result.faithfulness,
            answer_correctness=result.answer_correctness,
            has_ground_truth=ground_truth is not None,
        )
