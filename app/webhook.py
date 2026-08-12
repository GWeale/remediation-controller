"""GitHub webhook signature verification and event filtering."""

import hashlib
import hmac
from typing import Any, Optional


def verify_signature(secret: str, payload: bytes, signature_header: Optional[str]) -> bool:
    """Validate the X-Hub-Signature-256 header against the request body."""
    if not secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header.removeprefix("sha256="), expected)


def extract_labeled_issue(
    event: str, payload: dict[str, Any], target_repo: str, trigger_label: str
) -> Optional[dict[str, Any]]:
    """Return issue info when the event is a matching `issues.labeled` action.

    Returns None for anything that should be ignored.
    """
    if event != "issues" or payload.get("action") != "labeled":
        return None
    repo = payload.get("repository", {}).get("full_name")
    if repo != target_repo:
        return None
    if payload.get("label", {}).get("name") != trigger_label:
        return None
    issue = payload.get("issue") or {}
    number = issue.get("number")
    if not isinstance(number, int):
        return None
    return {
        "repo": repo,
        "issue_number": number,
        "issue_title": issue.get("title") or "",
        "issue_url": issue.get("html_url") or "",
        "label": trigger_label,
    }
