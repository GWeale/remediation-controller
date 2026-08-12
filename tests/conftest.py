import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient

SECRET = "test-webhook-secret"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("DEVIN_API_KEY", "test-key")
    monkeypatch.setenv("DEVIN_ORG_ID", "org-test")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "runs.db"))
    monkeypatch.setenv("TARGET_REPO", "GWeale/superset")
    monkeypatch.setenv("TRIGGER_LABEL", "devin:ready")
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "3600")

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def labeled_issue_payload(
    repo: str = "GWeale/superset",
    label: str = "devin:ready",
    number: int = 1,
    action: str = "labeled",
) -> bytes:
    return json.dumps(
        {
            "action": action,
            "label": {"name": label},
            "repository": {"full_name": repo},
            "issue": {
                "number": number,
                "title": "Expand stack yields NaN",
                "html_url": f"https://github.com/{repo}/issues/{number}",
            },
        }
    ).encode()
