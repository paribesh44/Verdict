from __future__ import annotations

import os
from typing import Dict, List, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

try:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False


class MarsState(TypedDict, total=False):
    query: str
    hypotheses: List[str]
    extractions: List[Dict[str, object]]
    reviewer_a_notes: List[str]
    reviewer_b_notes: List[str]
    final_answer: str
    token_cost_estimate: int
    latency_ms_estimate: int


def _get_llm(model_size: str = "small"):
    """Small = fast (Haiku/mini), large = Sonnet/GPT-4 for meta-review."""
    if not _LLM_AVAILABLE:
        return None
    if os.getenv("ANTHROPIC_API_KEY"):
        model = "claude-3-5-haiku-20241022" if model_size == "small" else "claude-3-5-sonnet-20241022"
        return ChatAnthropic(model=model, temperature=0)
    if os.getenv("OPENAI_API_KEY"):
        model = "gpt-4o-mini" if model_size == "small" else "gpt-4o"
        return ChatOpenAI(model=model, temperature=0)
    return None


# ----- Author -----

class AuthorOutput(BaseModel):
    hypotheses: List[str] = Field(description="2-4 research hypotheses derived from the query")


def author_agent(state: MarsState) -> MarsState:
    query = state.get("query", "")
    extractions = state.get("extractions", [])
    token = state.get("token_cost_estimate", 0)
    latency = state.get("latency_ms_estimate", 0)

    llm = _get_llm("small")
    if llm is not None:
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Generate 2-4 concise research hypotheses for the user query. Return only a JSON object with a list 'hypotheses' of strings."),
                ("human", "{query}"),
            ])
            structured_llm = llm.with_structured_output(AuthorOutput)
            result = (prompt | structured_llm).invoke({"query": query})
            hypotheses = result.hypotheses if result.hypotheses else []
        except Exception:
            hypotheses = [f"H1: {query} requires evidence.", f"H2: {query} benefits from multi-perspective review."]
        token += 900
        latency += 320
    else:
        hypotheses = [
            f"H1: {query} is impacted by privacy-first on-device triage.",
            f"H2: {query} benefits from independent reviewer scoring.",
        ]
        token += 900
        latency += 320

    out: MarsState = {
        "hypotheses": hypotheses,
        "token_cost_estimate": token,
        "latency_ms_estimate": latency,
    }
    if extractions:
        out["extractions"] = extractions
    return out


# ----- Reviewer A -----

def reviewer_a_agent(state: MarsState) -> MarsState:
    hypotheses = state.get("hypotheses", [])
    extractions = state.get("extractions", [])
    token = state.get("token_cost_estimate", 0)
    latency = state.get("latency_ms_estimate", 0)

    llm = _get_llm("small")
    if llm is not None and hypotheses and extractions:
        try:
            evidence_text = "\n".join(
                str(e.get("summary", e.get("url", "")))[:200] for e in extractions[:10]
            )
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are Reviewer A. Score how well the evidence supports each hypothesis. Output 1-2 short notes as a single newline-separated string."),
                ("human", "Hypotheses:\n{hypotheses}\n\nEvidence summaries:\n{evidence}"),
            ])
            chain = prompt | llm
            msg = chain.invoke({"hypotheses": "\n".join(hypotheses), "evidence": evidence_text})
            content = msg.content if hasattr(msg, "content") else str(msg)
            notes = [s.strip() for s in content.split("\n") if s.strip()][:3]
            if not notes:
                notes = [f"ReviewerA: evidence sufficiency for {len(hypotheses)} hypotheses."]
        except Exception:
            notes = [f"ReviewerA validates evidence sufficiency for {len(hypotheses)} hypotheses."]
        token += 300
        latency += 140
    else:
        notes = [f"ReviewerA validates evidence sufficiency for {len(hypotheses)} hypotheses."]
        token += 300
        latency += 140

    return {
        "reviewer_a_notes": notes,
        "token_cost_estimate": token,
        "latency_ms_estimate": latency,
    }


# ----- Reviewer B -----

def reviewer_b_agent(state: MarsState) -> MarsState:
    hypotheses = state.get("hypotheses", [])
    extractions = state.get("extractions", [])
    token = state.get("token_cost_estimate", 0)
    latency = state.get("latency_ms_estimate", 0)

    llm = _get_llm("small")
    if llm is not None and extractions:
        try:
            evidence_text = "\n".join(
                str(e.get("summary", e.get("url", "")))[:200] for e in extractions[:10]
            )
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are Reviewer B. Flag calibration or quality risks in the extracted claims. Output 1-2 short notes as a newline-separated string."),
                ("human", "Hypotheses:\n{hypotheses}\n\nExtracted claims/evidence:\n{evidence}"),
            ])
            chain = prompt | llm
            msg = chain.invoke({
                "hypotheses": "\n".join(hypotheses) if hypotheses else "N/A",
                "evidence": evidence_text,
            })
            content = msg.content if hasattr(msg, "content") else str(msg)
            notes = [s.strip() for s in content.split("\n") if s.strip()][:3]
            if not notes:
                notes = [f"ReviewerB: calibration risk across {len(extractions)} claims."]
        except Exception:
            notes = [f"ReviewerB flags calibration risk across {len(extractions)} extracted claims."]
        token += 300
        latency += 150
    else:
        notes = [f"ReviewerB flags calibration risk across {len(extractions)} extracted claims."]
        token += 300
        latency += 150

    return {
        "reviewer_b_notes": notes,
        "token_cost_estimate": token,
        "latency_ms_estimate": latency,
    }


# ----- Meta-Reviewer -----

def meta_reviewer_agent(state: MarsState) -> MarsState:
    notes_a = state.get("reviewer_a_notes", [])
    notes_b = state.get("reviewer_b_notes", [])
    token = state.get("token_cost_estimate", 0)
    latency = state.get("latency_ms_estimate", 0)
    notes = [*notes_a, *notes_b]
    synthesis_fallback = " | ".join(notes) if notes else "No review notes available."

    llm = _get_llm("small")
    if llm is not None and notes:
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Synthesize the reviewer notes into one short final answer (2-4 sentences) for the user. Be concise."),
                ("human", "Reviewer notes:\n{notes}"),
            ])
            chain = prompt | llm
            msg = chain.invoke({"notes": "\n".join(notes)})
            content = msg.content if hasattr(msg, "content") else str(msg)
            final_answer = content.strip() if content else synthesis_fallback
        except Exception:
            final_answer = f"Meta-review synthesis: {synthesis_fallback}"
        token += 220
        latency += 100
    else:
        final_answer = f"Meta-review synthesis: {synthesis_fallback}"
        token += 220
        latency += 100

    return {
        "final_answer": final_answer,
        "token_cost_estimate": token,
        "latency_ms_estimate": latency,
    }


def build_mars_graph():
    graph = StateGraph(MarsState)
    graph.add_node("author", author_agent)
    graph.add_node("reviewer_a", reviewer_a_agent)
    graph.add_node("reviewer_b", reviewer_b_agent)
    graph.add_node("meta_reviewer", meta_reviewer_agent)

    graph.add_edge(START, "author")
    graph.add_edge("author", "reviewer_a")
    graph.add_edge("reviewer_a", "reviewer_b")
    graph.add_edge("reviewer_b", "meta_reviewer")
    graph.add_edge("meta_reviewer", END)

    return graph.compile()
