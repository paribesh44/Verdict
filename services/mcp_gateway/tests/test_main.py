from fastapi.testclient import TestClient

from mcp_gateway.main import app

client = TestClient(app)


def test_health_exposes_supported_tools():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "firecrawl.agent.search" in payload["supportedTools"]


def _identity_headers(actor_id: str = "user-1", intent: str = "research_navigation") -> dict:
    return {"X-Actor-Id": actor_id, "X-Intent": intent}


def test_invoke_rejects_unknown_tool():
    response = client.post(
        "/",
        json={
            "actorId": "user-1",
            "intent": "research_navigation",
            "toolName": "unknown.tool",
            "input": {"query": "test"},
        },
        headers=_identity_headers(),
    )
    assert response.status_code == 400
    assert "Unsupported tool" in response.json()["detail"]


def test_invoke_rejects_missing_actor_header():
    response = client.post(
        "/",
        json={
            "actorId": "user-1",
            "intent": "research_navigation",
            "toolName": "firecrawl.agent.search",
            "input": {"query": "test"},
        },
        headers={"X-Intent": "research_navigation"},
    )
    assert response.status_code == 401
    assert "X-Actor-Id" in response.json()["detail"]


def test_invoke_rejects_disallowed_intent():
    response = client.post(
        "/",
        json={
            "actorId": "user-1",
            "intent": "database_write",
            "toolName": "firecrawl.agent.search",
            "input": {"query": "test"},
        },
        headers=_identity_headers(intent="database_write"),
    )
    assert response.status_code == 403


def test_invoke_rejects_missing_query():
    response = client.post(
        "/",
        json={
            "actorId": "user-1",
            "intent": "research_navigation",
            "toolName": "firecrawl.agent.search",
            "input": {},
        },
        headers=_identity_headers(),
    )
    assert response.status_code == 400
    assert "input.query is required" in response.json()["detail"]


def test_invoke_routes_to_firecrawl(monkeypatch):
    async def fake_firecrawl_search(query: str, depth: int):
        assert query == "what is mcp"
        assert depth == 2
        return {
            "provider": "firecrawl",
            "results": [{"title": "Mock", "url": "https://example.org", "summary": "ok"}],
            "raw": {"data": [{"title": "Mock"}]},
        }

    monkeypatch.setattr("mcp_gateway.main._firecrawl_search", fake_firecrawl_search)

    response = client.post(
        "/v1/tools/invoke",
        json={
            "actorId": "user-1",
            "intent": "research_navigation",
            "toolName": "firecrawl.agent.search",
            "input": {"query": "what is mcp", "depth": 2},
        },
        headers=_identity_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["provider"] == "firecrawl"
    assert payload["data"]["results"][0]["title"] == "Mock"
