from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List
from uuid import uuid4

from dotenv import load_dotenv
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

# FIX: Import the new extract_claims function
from app.tools.firecrawl import autonomous_research, extract_claims
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

# FIX: Add extract tool to allowed tools policy
ALLOWED_TOOLS = {"firecrawl.agent.search", "firecrawl.extract"}
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
    trace_id = str(uuid4())
    request_id = str(uuid4())

    async def event_generator() -> AsyncIterator[str]:
        triage = local_slm_triage(request.query)
        
        # Initial Status Update
        yield _sse_payload({"kind": "aguiEvent", "event": _agui_event(trace_id, "STATE_DELTA", {"path": "/research/status", "op": "replace", "value": "running"})})

        # Redaction Logic
        query_for_pipeline = PIIRedactor().redact(request.query) if triage.route == "local_only" else request.query
        
        if query_for_pipeline != request.query:
            yield _sse_payload({
                "kind": "aguiEvent",
                "event": _agui_event(trace_id, "TEXT_MESSAGE_CONTENT", {
                    "role": "security",
                    "content": f"🔒 Sensitive data redacted. Safe query: \"{query_for_pipeline}\""
                })
            })

        # Emit Surface Definitions
        yield _sse_payload({
            "kind": "a2uiEnvelope",
            "envelope": _a2ui_envelope(request_id, "surfaceUpdate", {
                "components": [
                    {"id": "status-card", "component": "StatusCard", "bindings": [{"prop": "value", "path": "/research/status"}], "props": {"title": "Pipeline Status"}},
                    {"id": "claims-list", "component": "ClaimsList", "bindings": [{"prop": "claims", "path": "/research/claims"}], "props": {"title": "Extracted Claims"}},
                    {"id": "efficiency-card", "component": "StatusCard", "bindings": [{"prop": "value", "path": "/research/efficiency/tokenGainRatio"}], "props": {"title": "MARS Token Gain Ratio"}},
                    {"id": "answer-surface", "component": "MessageSurface", "bindings": [{"prop": "content", "path": "/research/finalAnswer"}, {"prop": "role", "path": "/research/answerRole"}]}
                ]
            })
        })
        yield _sse_payload({"kind": "a2uiEnvelope", "envelope": _a2ui_envelope(request_id, "beginRendering", {"surfaceId": "main"})})

        evidence: List[Dict[str, Any]] = []
        mcp_client = MCPClient(endpoint=MCP_ENDPOINT)

        # Unified Research Block
        if triage.classification != "PRIVATE" and MCP_ENDPOINT:
            try:
                # Step 1: Search
                yield _sse_payload({"kind": "aguiEvent", "event": _agui_event(trace_id, "TOOL_CALL_START", {"toolName": "firecrawl.agent.search", "callId": str(uuid4()), "arguments": {"query": query_for_pipeline}})})
                search_result = await autonomous_research(mcp_client, identity.actor_id, query_for_pipeline)
                raw_results = search_result.get("data", {}).get("results", [])
                
                # Step 2: Extract (Try Deep Scrape)
                urls = [res["url"] for res in raw_results[:3] if res.get("url")]
                if urls:
                    yield _sse_payload({"kind": "aguiEvent", "event": _agui_event(trace_id, "TOOL_CALL_START", {"toolName": "firecrawl.extract", "callId": str(uuid4()), "arguments": {"urls": urls}})})
                    extract_res = await extract_claims(mcp_client, identity.actor_id, urls)
                    raw_ext = extract_res.get("data", {}).get("data", [])
                    for i, ext in enumerate(raw_ext):
                        content = ext.get("text", str(ext)) if isinstance(ext, dict) else str(ext)
                        evidence.append({"url": urls[i], "summary": content, "confidence": 0.9})
                
                # Fallback to search snippets if extraction was empty
                if not evidence:
                    evidence = raw_results
            except Exception as e:
                print(f"Research failed: {e}")
                evidence = []

        # Scaffold Fallback
        if not evidence:
            evidence = [{"summary": "System operating in scaffold mode.", "url": "N/A", "confidence": 0.5}]

        # Extraction and Graph Execution
        extraction = schema_locked_extract(query_for_pipeline, evidence)
        initial_state = {"query": query_for_pipeline, "extractions": evidence}
        accumulated = dict(initial_state)

        async for chunk in mars_graph.astream(initial_state, stream_mode="updates"):
            for node_name, state_update in chunk.items():
                yield _sse_payload({"kind": "aguiEvent", "event": _agui_event(trace_id, "STATE_DELTA", {"path": f"/research/graph/nodes/{node_name}", "op": "replace", "value": {"status": "running"}})})
                accumulated.update(state_update)
                yield _sse_payload({"kind": "aguiEvent", "event": _agui_event(trace_id, "STATE_DELTA", {"path": f"/research/graph/nodes/{node_name}", "op": "replace", "value": {"status": "completed", "metrics": {"tokens": state_update.get("token_cost_estimate", 0), "latency": state_update.get("latency_ms_estimate", 0)/1000}}})})

        # Final UI Update
        efficiency = compare_mars_vs_mad(int(accumulated.get("token_cost_estimate", 1)), int(accumulated.get("latency_ms_estimate", 1)))
        yield _sse_payload({"kind": "a2uiEnvelope", "envelope": _a2ui_envelope(request_id, "dataModelUpdate", {"updates": [
            {"path": "/research/status", "op": "replace", "value": "completed"},
            {"path": "/research/claims", "op": "replace", "value": [c.text for c in extraction.claims]},
            {"path": "/research/finalAnswer", "op": "replace", "value": accumulated.get("final_answer", "Done.")},
            {"path": "/research/answerRole", "op": "replace", "value": "assistant"},
            {"path": "/research/efficiency", "op": "replace", "value": {"tokenGainRatio": round(efficiency.token_gain_ratio, 2)}}
        ]})})

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