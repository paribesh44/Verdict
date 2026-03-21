from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

try:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False

try:
    from langchain_ollama import ChatOllama
    _OLLAMA_AVAILABLE = True
except ImportError:
    _OLLAMA_AVAILABLE = False


@dataclass
class TriageResult:
    summary: str
    privacy_sensitive: bool
    route: str
    classification: Literal["SENSITIVE", "PRIVATE", "GENERAL"]


class TriageClassification(BaseModel):
    """Structured output for SLM triage."""

    classification: Literal["SENSITIVE", "PRIVATE", "GENERAL"] = Field(
        description="SENSITIVE if the query involves credentials, PII, or high-risk actions; "
        "PRIVATE if it involves personal or confidential data; GENERAL otherwise."
    )


def _get_triage_llm():
    """Use a small/fast model. Prefer Anthropic Haiku, OpenAI mini, then Ollama (local)."""
    if not _LLM_AVAILABLE:
        return None
    if os.getenv("ANTHROPIC_API_KEY"):
        return ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            temperature=0,
        ).with_structured_output(TriageClassification)
    if os.getenv("OPENAI_API_KEY"):
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
        ).with_structured_output(TriageClassification)
    if _OLLAMA_AVAILABLE and os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOllama(
            model=os.getenv("OLLAMA_TRIAGE_MODEL", "llama3.2"),
            base_url=base_url,
            temperature=0,
        ).with_structured_output(TriageClassification)
    return None


def local_slm_triage(query: str) -> TriageResult:
    summary = query[:200] if len(query) > 200 else query
    llm = _get_triage_llm()
    if llm is None:
        # Fallback: keyword-based when no API key
        lowered = query.lower()
        sensitive = (
            "ssn" in lowered
            or "credential" in lowered
            or "private" in lowered
            or "password" in lowered
        )
        classification: Literal["SENSITIVE", "PRIVATE", "GENERAL"] = (
            "SENSITIVE" if sensitive else "GENERAL"
        )
    else:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Classify the user query into exactly one of: SENSITIVE (credentials, PII, "
                    "high-risk actions), PRIVATE (personal/confidential data), GENERAL (safe for "
                    "agentic research). Respond only with the classification.",
                ),
                ("human", "{query}"),
            ]
        )
        chain = prompt | llm
        result = chain.invoke({"query": query})
        classification = result.classification

    privacy_sensitive = classification in ("SENSITIVE", "PRIVATE")
    route = "local_only" if privacy_sensitive else "agentic_rag"
    return TriageResult(
        summary=summary,
        privacy_sensitive=privacy_sensitive,
        route=route,
        classification=classification,
    )
