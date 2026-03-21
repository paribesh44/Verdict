from __future__ import annotations

import os
from typing import Any, Dict, List

from .schemas import Citation, ClaimExtraction, ExtractionBundle

try:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False


def _format_evidence(evidence: List[Dict[str, Any]]) -> str:
    parts = []
    for i, item in enumerate(evidence, 1):
        url = item.get("url", "about:blank")
        summary = item.get("summary", item.get("description", ""))
        quote = item.get("quote", summary[:200] if summary else "")
        parts.append(f"[{i}] URL: {url}\nSummary: {summary}\nQuote: {quote}")
    return "\n\n".join(parts) if parts else "(no evidence)"


def _get_extraction_llm():
    """LLM for structured claim extraction. Prefer Anthropic then OpenAI."""
    if not _LLM_AVAILABLE:
        return None
    
    # We set max_tokens to 2048 to provide ample 'runway' for full sentences
    if os.getenv("ANTHROPIC_API_KEY"):
        return ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            temperature=0,
            max_tokens=2048, 
        ).with_structured_output(ExtractionBundle)
        
    if os.getenv("OPENAI_API_KEY"):
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=2048,
        ).with_structured_output(ExtractionBundle)
        
    return None

def _extract_via_llm(query: str, evidence: List[Dict[str, Any]]) -> ExtractionBundle | None:
    llm = _get_extraction_llm()
    if llm is None:
        return None
    
    # Updated prompt to explicitly forbid half-finished thoughts
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a precision research assistant. Extract structured claims from the provided evidence.\n\n"
                "STRICT RULES:\n"
                "1. Every claim 'text' MUST be a 100% complete, grammatically correct sentence.\n"
                "2. DO NOT truncate sentences. DO NOT end with '...'.\n"
                "3. If a sentence from the source is cut off, use the surrounding context to finish the thought logically.\n"
                "4. Ensure every claim ends with a period (.) or appropriate punctuation."
            ),
            ("human", "Query: {query}\n\nEvidence:\n{evidence}"),
        ]
    )
    chain = prompt | llm
    evidence_text = _format_evidence(evidence)
    try:
        result = chain.invoke({"query": query, "evidence": evidence_text})
        if result and result.claims:
            return result
    except Exception as e:
        print(f"Extraction failed: {e}")
        pass
    return None


def _fallback_extract(query: str, evidence: List[Dict[str, Any]]) -> ExtractionBundle:
    """
    High-fidelity fallback: Returns the raw evidence without stripping or 
    truncating any words if the Cloud LLM is unavailable.
    """
    claims: List[ClaimExtraction] = []
    
    for index, item in enumerate(evidence):
        # 1. Get the raw text from the 'summary' or 'content' field
        # We NO LONGER use [:200] or any character caps here.
        text = str(item.get("summary", item.get("content", ""))).strip()
        
        if not text:
            continue

        # 2. Build the claim using the full, unstripped text
        claims.append(
            ClaimExtraction(
                claim_id=f"claim-{index + 1}",
                text=text, # <--- Full text returned as-is
                confidence=float(item.get("confidence", 0.7)),
                citations=[
                    Citation(
                        source_url=str(item.get("url", "about:blank")),
                        quote=text, # <--- Full quote returned as-is
                    )
                ],
            )
        )
        
    return ExtractionBundle(query=query, claims=claims)


def schema_locked_extract(query: str, evidence: List[Dict[str, Any]]) -> ExtractionBundle:
    result = _extract_via_llm(query, evidence)
    if result is not None:
        return result
    return _fallback_extract(query, evidence)