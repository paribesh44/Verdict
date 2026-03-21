from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Set

from dotenv import load_dotenv

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

# Load .env from repo root
_env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_dotenv(_env_path)

# 1. FIX: Added firecrawl.extract to the allowed tools and intents
SUPPORTED_TOOLS: Set[str] = {"firecrawl.agent.search", "firecrawl.extract"}
ALLOWED_INTENTS: Dict[str, Set[str]] = {
    "firecrawl.agent.search": {"research_navigation"},
    "firecrawl.extract": {"research_extraction"}
}

app = FastAPI(title="Verdict MCP Gateway", version="0.1.0")


class ToolRequest(BaseModel):
    actor_id: str = Field(alias="actorId")
    intent: str
    tool_name: str = Field(alias="toolName")
    input: Dict[str, Any]
    approval_id: str | None = Field(default=None, alias="approvalId")

    model_config = ConfigDict(populate_by_name=True)


def _verify_actor_identity(
    request: ToolRequest,
    x_actor_id: str | None,
    x_intent: str | None,
) -> None:
    """Zero trust: require headers to match body. Reject if missing or mismatch."""
    if not x_actor_id or not x_actor_id.strip():
        raise HTTPException(status_code=401, detail="X-Actor-Id header is required.")
    if not x_intent or not x_intent.strip():
        raise HTTPException(status_code=401, detail="X-Intent header is required.")
    if x_actor_id.strip() != request.actor_id:
        raise HTTPException(status_code=403, detail="X-Actor-Id does not match request body.")
    if x_intent.strip() != request.intent:
        raise HTTPException(status_code=403, detail="X-Intent does not match request body.")


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _first_non_empty(item: Dict[str, Any], keys: List[str]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _normalize_results(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        raw_results = payload["results"]
    elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
        raw_results = payload["data"]
    elif (
        isinstance(payload, dict)
        and isinstance(payload.get("data"), dict)
        and isinstance(payload["data"].get("results"), list)
    ):
        raw_results = payload["data"]["results"]
    elif isinstance(payload, list):
        raw_results = payload
    else:
        raw_results = []

    normalized: List[Dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = _first_non_empty(item, ["url", "sourceUrl", "link"])
        summary = _first_non_empty(item, ["description", "snippet", "markdown", "content"])
        normalized.append(
            {
                "title": _first_non_empty(item, ["title", "metadataTitle"]) or "Untitled result",
                "url": url,
                "summary": summary,
                "confidence": 0.75,
            }
        )

    return normalized


async def _firecrawl_search(query: str, depth: int) -> Dict[str, Any]:
    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="FIRECRAWL_API_KEY is not configured on the MCP gateway.",
        )

    base_url = os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev").strip().rstrip("/")
    timeout_seconds = float(os.getenv("FIRECRAWL_TIMEOUT_SECONDS", "20"))
    limit = _bounded_int(depth * 3, default=5, minimum=3, maximum=10)

    payload = {"query": query, "limit": limit}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(f"{base_url}/v1/search", json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        message = exc.response.text[:500]
        raise HTTPException(
            status_code=502,
            detail=f"Firecrawl search failed with status {exc.response.status_code}: {message}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Firecrawl transport error: {exc}") from exc

    try:
        raw_payload = response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Firecrawl returned non-JSON response.")

    return {
        "provider": "firecrawl",
        "results": _normalize_results(raw_payload),
        "raw": raw_payload,
    }


# 2. FIX: New function to handle deep extraction of the actual URLs
async def _firecrawl_extract(urls: List[str], prompt: str) -> Dict[str, Any]:
    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="FIRECRAWL_API_KEY is not configured on the MCP gateway.",
        )

    base_url = os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev").strip().rstrip("/")
    # Extractions take longer than simple searches, increasing timeout slightly
    timeout_seconds = float(os.getenv("FIRECRAWL_TIMEOUT_SECONDS", "45")) 

    payload = {
        "urls": urls,
        "prompt": prompt
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(f"{base_url}/v1/extract", json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        message = exc.response.text[:500]
        raise HTTPException(
            status_code=502,
            detail=f"Firecrawl extract failed with status {exc.response.status_code}: {message}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Firecrawl transport error: {exc}") from exc

    try:
        raw_payload = response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Firecrawl returned non-JSON response.")

    return {
        "provider": "firecrawl",
        "data": raw_payload.get("data", []),
        "raw": raw_payload,
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "supportedTools": sorted(SUPPORTED_TOOLS),
        "providerConfigured": {"firecrawl": bool(os.getenv("FIRECRAWL_API_KEY", "").strip())},
    }


@app.post("/")
@app.post("/v1/tools/invoke")
async def invoke_tool(
    request: ToolRequest,
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    x_intent: str | None = Header(default=None, alias="X-Intent"),
) -> Dict[str, Any]:
    _verify_actor_identity(request, x_actor_id, x_intent)
    if request.tool_name not in SUPPORTED_TOOLS:
        raise HTTPException(status_code=400, detail=f"Unsupported tool: {request.tool_name}")

    allowed_intents = ALLOWED_INTENTS.get(request.tool_name, set())
    if request.intent not in allowed_intents:
        raise HTTPException(
            status_code=403,
            detail=f"Intent '{request.intent}' is not allowed for tool '{request.tool_name}'.",
        )

    # Dispatch to Search
    if request.tool_name == "firecrawl.agent.search":
        query = str(request.input.get("query", "")).strip()
        if not query:
            raise HTTPException(status_code=400, detail="input.query is required.")

        depth = _bounded_int(request.input.get("depth"), default=2, minimum=1, maximum=5)
        data = await _firecrawl_search(query=query, depth=depth)
        return {"ok": True, "data": data}

    # 3. FIX: Dispatch to Extract
    if request.tool_name == "firecrawl.extract":
        urls = request.input.get("urls", [])
        prompt = str(request.input.get("prompt", "")).strip()
        if not urls or not isinstance(urls, list):
             raise HTTPException(status_code=400, detail="input.urls must be a valid list of strings.")

        data = await _firecrawl_extract(urls=urls, prompt=prompt)
        return {"ok": True, "data": data}

    raise HTTPException(status_code=500, detail="Tool dispatch failed unexpectedly.")