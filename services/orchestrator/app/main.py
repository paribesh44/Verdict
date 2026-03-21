from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from typing import Any, AsyncIterator, Dict, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.eval.auditor import AuditPlane
from app.state_backends import get_approval_store, get_extraction_store, get_trajectory_logger
from app.graphs.efficiency import compare_mars_vs_mad
from app.graphs.mars_graph import build_mars_graph
from app.rag.pipeline import schema_locked_extract
from app.security.identity import verify_identity
from app.security.policy import evaluate_tool_call
from app.security.redact import PIIRedactor
from app.slm.triage import local_slm_triage
from app.tools.firecrawl import autonomous_research
from app.tools.mcp import MCPClient

# Load .env: repo root (from this file's path), then cwd so running from Verdict root wins
_env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_dotenv(_env_path)
load_dotenv(Path.cwd() / ".env")

app = FastAPI(title="Verdict Orchestrator", version="0.1.0")

cors_origins_raw = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
CORS_ALLOW_ORIGINS = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

trajectory_logger = get_trajectory_logger()
approval_store = get_approval_store()
extraction_store = get_extraction_store()
mars_graph = build_mars_graph()


def _get_audit_plane() -> AuditPlane:
    return AuditPlane(
        get_extraction=extraction_store.get,
        get_trajectory_steps=trajectory_logger.get_steps_for_trace,
    )

ALLOWED_TOOLS = {"firecrawl.agent.search"}
MCP_ENDPOINT = os.getenv("MCP_GATEWAY_URL", "")


class ResearchRequest(BaseModel):
    query: str
    actor_id: str = Field(alias="actorId")
    intent: str
    approval_id: str | None = Field(default=None, alias="approvalId")

    model_config = ConfigDict(populate_by_name=True)


class ApprovalRequest(BaseModel):
    approved: bool


class AuditRequest(BaseModel):
    trace_id: str = Field(alias="traceId")
    ground_truth: str | None = Field(default=None, alias="groundTruth")

    model_config = ConfigDict(populate_by_name=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sse_payload(data: Dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _agui_event(trace_id: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "eventId": str(uuid4()),
        "traceId": trace_id,
        "timestamp": _now(),
        "eventType": event_type,
        "payload": payload,
    }


def _a2ui_envelope(request_id: str, envelope_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"requestId": request_id, "timestamp": _now(), "type": envelope_type, **payload}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/approvals/{approval_id}")
async def set_approval(approval_id: str, request: ApprovalRequest) -> Dict[str, Any]:
    ticket = await approval_store.get(approval_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Approval ticket not found.")
    try:
        if request.approved:
            await approval_store.approve(approval_id)
            return {"approvalId": ticket.approval_id, "approved": True}
        await approval_store.deny(approval_id)
        return {"approvalId": ticket.approval_id, "approved": False}
    except KeyError:
        raise HTTPException(status_code=404, detail="Approval ticket not found.")


@app.post("/v1/research/stream")
async def stream_research(request: ResearchRequest) -> StreamingResponse:
    identity = verify_identity(request.actor_id, request.intent)
    if request.approval_id:
        ticket_for_resume = await approval_store.get(request.approval_id)
        if ticket_for_resume and ticket_for_resume.denied:
            raise HTTPException(
                status_code=400,
                detail="Approval was denied. Start a new research request.",
            )
    trace_id = str(uuid4())
    request_id = str(uuid4())

    async def event_generator() -> AsyncIterator[str]:
        triage = local_slm_triage(request.query)
        await trajectory_logger.record(
            trace_id=trace_id,
            step_name="local_slm_triage",
            precision=0.8,
            recall=0.72,
            token_estimate=120,
            latency_ms=45,
        )

        yield _sse_payload(
            {
                "kind": "aguiEvent",
                "event": _agui_event(
                    trace_id,
                    "TEXT_MESSAGE_CONTENT",
                    {"role": "assistant", "content": f"Triage route: {triage.route}"},
                ),
            }
        )
        yield _sse_payload(
            {
                "kind": "aguiEvent",
                "event": _agui_event(
                    trace_id,
                    "STATE_DELTA",
                    {"path": "/research/status", "op": "replace", "value": "running"},
                ),
            }
        )

        # PRIVATE-route guardrail: block MCP and notify user.
        if triage.classification == "PRIVATE":
            yield _sse_payload(
                {
                    "kind": "aguiEvent",
                    "event": _agui_event(
                        trace_id,
                        "TEXT_MESSAGE_CONTENT",
                        {
                            "role": "assistant",
                            "content": "Privacy-mode enforcement is active. External tool calls (MCP) are blocked for this request.",
                        },
                    ),
                }
            )

        # Redact PII when route is local_only before passing query to MARS/extraction.
        query_for_pipeline = (
            PIIRedactor().redact(request.query) if triage.route == "local_only" else request.query
        )

        # Emit the trusted surface definitions first, then begin rendering.
        yield _sse_payload(
            {
                "kind": "a2uiEnvelope",
                "envelope": _a2ui_envelope(
                    request_id,
                    "surfaceUpdate",
                    {
                        "components": [
                            {
                                "id": "status-card",
                                "component": "StatusCard",
                                "bindings": [{"prop": "value", "path": "/research/status"}],
                                "props": {"title": "Pipeline Status"},
                            },
                            {
                                "id": "claims-list",
                                "component": "ClaimsList",
                                "bindings": [{"prop": "claims", "path": "/research/claims"}],
                                "props": {"title": "Extracted Claims"},
                            },
                            {
                                "id": "efficiency-card",
                                "component": "StatusCard",
                                "bindings": [{"prop": "value", "path": "/research/efficiency/tokenGainRatio"}],
                                "props": {"title": "MARS Token Gain Ratio"},
                            },
                            {
                                "id": "answer-surface",
                                "component": "MessageSurface",
                                "bindings": [
                                    {"prop": "content", "path": "/research/finalAnswer"},
                                    {"prop": "role", "path": "/research/answerRole"},
                                ],
                            },
                        ]
                    },
                ),
            }
        )
        yield _sse_payload(
            {
                "kind": "a2uiEnvelope",
                "envelope": _a2ui_envelope(request_id, "beginRendering", {"surfaceId": "main"}),
            }
        )

        evidence: List[Dict[str, Any]] = []
        decision = evaluate_tool_call(
            identity=identity,
            tool_name="firecrawl.agent.search",
            declared_intent=identity.intent,
            allowed_tools=ALLOWED_TOOLS,
        )
        await trajectory_logger.record(
            trace_id=trace_id,
            step_name="policy_gate",
            precision=0.9 if decision.allowed else 0.7,
            recall=0.85 if decision.allowed else 0.6,
            token_estimate=40,
            latency_ms=12,
        )

        if decision.allowed and MCP_ENDPOINT and triage.classification != "PRIVATE":
            yield _sse_payload(
                {
                    "kind": "aguiEvent",
                    "event": _agui_event(
                        trace_id,
                        "TOOL_CALL_START",
                        {
                            "toolName": "firecrawl.agent.search",
                            "callId": str(uuid4()),
                            "arguments": {"query": request.query, "depth": 2},
                        },
                    ),
                }
            )
            mcp_client = MCPClient(endpoint=MCP_ENDPOINT)
            try:
                tool_result = await autonomous_research(
                    mcp_client,
                    identity.actor_id,
                    request.query,
                    approval_id=request.approval_id,
                )
                evidence = tool_result.get("data", {}).get("results", [])
            except Exception:
                evidence = []

        if not evidence:
            evidence = [
                {
                    "summary": "Synthetic evidence generated in scaffold mode.",
                    "url": "https://example.org/synthetic",
                    "quote": "Scaffold evidence quote.",
                    "confidence": 0.68,
                }
            ]

        # HITL gate for explicitly sensitive requests.
        is_sensitive_request = "write" in request.query.lower() or "database" in request.query.lower()
        has_valid_approval = bool(request.approval_id and (await approval_store.is_approved(request.approval_id)))
        if is_sensitive_request and not has_valid_approval:
            ticket = await approval_store.create(
                trace_id=trace_id,
                reason="Sensitive write-like request detected.",
                requested_action="database_write",
            )
            yield _sse_payload(
                {
                    "kind": "aguiEvent",
                    "event": _agui_event(
                        trace_id,
                        "INTERRUPT",
                        {
                            "approvalId": ticket.approval_id,
                            "reason": ticket.reason,
                            "requestedAction": ticket.requested_action,
                        },
                    ),
                }
            )
            return

        extraction = schema_locked_extract(query_for_pipeline, evidence)
        await trajectory_logger.record(
            trace_id=trace_id,
            step_name="schema_extraction",
            precision=0.91,
            recall=0.83,
            token_estimate=180,
            latency_ms=70,
        )
        initial_state: Dict[str, Any] = {
            "query": query_for_pipeline,
            "extractions": evidence,
        }
        accumulated: Dict[str, Any] = dict(initial_state)
        async for chunk in mars_graph.astream(initial_state, stream_mode="updates"):
            for node_name, state_update in chunk.items():
                yield _sse_payload(
                    {
                        "kind": "aguiEvent",
                        "event": _agui_event(
                            trace_id,
                            "STATE_DELTA",
                            {
                                "path": f"/research/graph/nodes/{node_name}",
                                "op": "replace",
                                "value": {"status": "running"},
                            },
                        ),
                    }
                )
                tokens = int(state_update.get("token_cost_estimate", 0))
                latency_ms = int(state_update.get("latency_ms_estimate", 0))
                yield _sse_payload(
                    {
                        "kind": "aguiEvent",
                        "event": _agui_event(
                            trace_id,
                            "STATE_DELTA",
                            {
                                "path": f"/research/graph/nodes/{node_name}",
                                "op": "replace",
                                "value": {
                                    "status": "completed",
                                    "metrics": {"tokens": tokens, "latency": latency_ms / 1000.0},
                                },
                            },
                        ),
                    }
                )
                accumulated.update(state_update)
        graph_state = accumulated
        final_answer = graph_state.get("final_answer", "No synthesis generated.")
        await extraction_store.set(trace_id, extraction, final_answer)
        efficiency = compare_mars_vs_mad(
            mars_tokens=int(graph_state.get("token_cost_estimate", 1)),
            mars_latency_ms=int(graph_state.get("latency_ms_estimate", 1)),
        )
        claims_text = [claim.text for claim in extraction.claims]

        await trajectory_logger.record(
            trace_id=trace_id,
            step_name="mars_pipeline",
            precision=0.86,
            recall=0.81,
            token_estimate=int(graph_state.get("token_cost_estimate", 0)),
            latency_ms=int(graph_state.get("latency_ms_estimate", 0)),
        )

        yield _sse_payload(
            {
                "kind": "a2uiEnvelope",
                "envelope": _a2ui_envelope(
                    request_id,
                    "dataModelUpdate",
                    {
                        "updates": [
                            {"path": "/research/status", "op": "replace", "value": "completed"},
                            {"path": "/research/claims", "op": "replace", "value": claims_text},
                            {
                                "path": "/research/finalAnswer",
                                "op": "replace",
                                "value": final_answer,
                            },
                            {"path": "/research/answerRole", "op": "replace", "value": "assistant"},
                            {
                                "path": "/research/efficiency",
                                "op": "replace",
                                "value": {
                                    "strategy": "MARS",
                                    "tokenGainRatio": round(efficiency.token_gain_ratio, 3),
                                    "latencyGainRatio": round(efficiency.latency_gain_ratio, 3),
                                },
                            },
                        ]
                    },
                ),
            }
        )
        yield _sse_payload(
            {
                "kind": "aguiEvent",
                "event": _agui_event(
                    trace_id,
                    "STATE_DELTA",
                    {"path": "/research/status", "op": "replace", "value": "completed"},
                ),
            }
        )
        yield _sse_payload(
            {
                "kind": "aguiEvent",
                "event": _agui_event(
                    trace_id,
                    "TEXT_MESSAGE_CONTENT",
                    {"role": "assistant", "content": final_answer},
                ),
            }
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/v1/trajectory/{trace_id}")
async def get_trajectory(trace_id: str) -> Dict[str, Any]:
    steps = await trajectory_logger.get_steps_for_trace(trace_id)
    return {"traceId": trace_id, "steps": steps}


@app.post("/v1/eval/audit")
async def post_audit(request: AuditRequest) -> Dict[str, Any]:
    plane = _get_audit_plane()
    result = await plane.audit(trace_id=request.trace_id, ground_truth=request.ground_truth)
    if result is None:
        raise HTTPException(status_code=404, detail="No extraction found for this trace_id.")
    return {
        "traceId": result.trace_id,
        "faithfulness": result.faithfulness,
        "answerCorrectness": result.answer_correctness,
        "hasGroundTruth": result.has_ground_truth,
    }
