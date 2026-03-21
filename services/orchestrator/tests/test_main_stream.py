import re

from fastapi.testclient import TestClient

from app.main import app


def test_sensitive_request_emits_interrupt_event():
    client = TestClient(app)
    response = client.post(
        "/v1/research/stream",
        json={"query": "Please write this into the database", "actorId": "user-1", "intent": "research"},
    )
    assert response.status_code == 200
    assert '"eventType": "INTERRUPT"' in response.text


def test_sensitive_request_can_resume_after_approval():
    client = TestClient(app)
    initial = client.post(
        "/v1/research/stream",
        json={"query": "Write this into the database", "actorId": "user-1", "intent": "research"},
    )
    match = re.search(r'"approvalId": "([^"]+)"', initial.text)
    assert match is not None
    approval_id = match.group(1)

    approved = client.post(f"/v1/approvals/{approval_id}", json={"approved": True})
    assert approved.status_code == 200
    assert approved.json()["approved"] is True

    resumed = client.post(
        "/v1/research/stream",
        json={
            "query": "Write this into the database",
            "actorId": "user-1",
            "intent": "research",
            "approvalId": approval_id,
        },
    )
    assert resumed.status_code == 200
    assert '"eventType": "INTERRUPT"' not in resumed.text
    assert '"type": "dataModelUpdate"' in resumed.text
