import json

import httpx
import pytest

from app.config import Settings
from app.devin_client import DevinClient, build_prompt


@pytest.mark.asyncio
async def test_create_session_sends_exact_path_and_body():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"session_id": "devin-xyz", "url": "https://app.devin.ai/sessions/xyz"},
        )

    settings = Settings(
        devin_api_key="test-key",
        devin_org_id="org-test",
        devin_api_base="https://api.devin.ai",
    )
    client = DevinClient(settings, transport=httpx.MockTransport(handler))

    issue_url = "https://github.com/GWeale/superset/issues/42"
    result = await client.create_session(
        prompt=build_prompt("GWeale/superset", 42, "title", issue_url),
        title="Remediate GWeale/superset#42",
        tags=["remediation-controller", "issue-42"],
        repo="GWeale/superset",
        issue_url=issue_url,
    )

    assert result["session_id"] == "devin-xyz"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.devin.ai/v3/organizations/org-test/sessions"
    assert captured["auth"] == "Bearer test-key"

    body = captured["body"]
    assert body["repos"] == ["GWeale/superset"]
    assert body["session_links"] == [issue_url]
    assert body["max_acu_limit"] == 3
    assert body["bypass_approval"] is True
    assert body["structured_output_required"] is False
    assert body["resumable"] is True
    assert body["tags"] == ["remediation-controller", "issue-42"]
    assert body["title"] == "Remediate GWeale/superset#42"
    assert "#42" in body["prompt"]
    assert "idempotent" not in body


@pytest.mark.asyncio
async def test_get_session_uses_session_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert (
            str(request.url)
            == "https://api.devin.ai/v3/organizations/org-test/sessions/devin-xyz"
        )
        assert request.method == "GET"
        return httpx.Response(200, json={"status": "running", "pull_requests": []})

    settings = Settings(
        devin_api_key="test-key",
        devin_org_id="org-test",
        devin_api_base="https://api.devin.ai",
    )
    client = DevinClient(settings, transport=httpx.MockTransport(handler))
    session = await client.get_session("devin-xyz")
    assert session["status"] == "running"
