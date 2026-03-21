from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, TypedDict
from uuid import uuid4


class ResearchClaim(TypedDict):
    claim_id: str
    text: str
    citations: List[str]
    confidence: float


class ResearchState(TypedDict, total=False):
    request_id: str
    trace_id: str
    query: str
    hypotheses: List[str]
    extractions: List[ResearchClaim]
    review_notes: List[str]
    final_answer: str
    trajectory_events: List[Dict[str, Any]]
    token_cost_estimate: int
    latency_ms_estimate: int


@dataclass
class RuntimeContext:
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
