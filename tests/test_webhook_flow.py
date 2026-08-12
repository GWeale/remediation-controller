import json
from unittest.mock import AsyncMock

from tests.conftest import labeled_issue_payload, sign


def post_webhook(client, body: bytes, signature: str | None = None, event: str = "issues"):
    headers = {"X-GitHub-Event": event, "Content-Type": "application/json"}
    if signature is not None:
        headers["X-Hub-Signature-256"] = signature
    return client.post("/webhook/github", content=body, headers=headers)


def test_rejects_invalid_signature(client):
    body = labeled_issue_payload()
    resp = post_webhook(client, body, signature="sha256=deadbeef")
    assert resp.status_code == 401


def test_rejects_missing_signature(client):
    resp = post_webhook(client, labeled_issue_payload())
    assert resp.status_code == 401


def test_ignores_other_events(client):
    body = labeled_issue_payload()
    resp = post_webhook(client, body, signature=sign(body), event="push")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ignored"}


def test_ignores_other_labels(client):
    body = labeled_issue_payload(label="bug")
    resp = post_webhook(client, body, signature=sign(body))
    assert resp.json() == {"status": "ignored"}


def test_ignores_other_repos(client):
    body = labeled_issue_payload(repo="someone/else")
    resp = post_webhook(client, body, signature=sign(body))
    assert resp.json() == {"status": "ignored"}


def test_creates_run_and_devin_session(client):
    client.app.state.devin.create_session = AsyncMock(
        return_value={
            "session_id": "devin-abc123",
            "url": "https://app.devin.ai/sessions/abc123",
        }
    )
    body = labeled_issue_payload(number=42)
    resp = post_webhook(client, body, signature=sign(body))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "created"
    assert data["devin_session_id"] == "devin-abc123"

    prompt = client.app.state.devin.create_session.call_args.kwargs["prompt"]
    assert "GWeale/superset" in prompt
    assert "#42" in prompt
    assert "NEVER merge pull requests" in prompt

    runs = client.get("/api/runs").json()
    assert len(runs) == 1
    assert runs[0]["status"] == "session_created"
    assert runs[0]["issue_number"] == 42


def test_duplicate_label_event_does_not_create_second_run(client):
    client.app.state.devin.create_session = AsyncMock(
        return_value={"session_id": "devin-abc", "url": "https://app.devin.ai/x"}
    )
    body = labeled_issue_payload(number=7)
    assert post_webhook(client, body, signature=sign(body)).json()["status"] == "created"
    assert post_webhook(client, body, signature=sign(body)).json()["status"] == "duplicate"
    assert len(client.get("/api/runs").json()) == 1


def test_failed_session_creation_marks_run_failed(client):
    client.app.state.devin.create_session = AsyncMock(side_effect=RuntimeError("api down"))
    body = labeled_issue_payload(number=9)
    resp = post_webhook(client, body, signature=sign(body))
    assert resp.status_code == 502
    runs = client.get("/api/runs").json()
    assert runs[0]["status"] == "failed"
    assert "api down" in runs[0]["error"]


def test_dashboard_renders(client):
    client.app.state.devin.create_session = AsyncMock(
        return_value={"session_id": "devin-abc", "url": "https://app.devin.ai/x"}
    )
    body = labeled_issue_payload(number=3)
    post_webhook(client, body, signature=sign(body))
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Remediation Controller" in resp.text
    assert "GWeale/superset#3" in resp.text
