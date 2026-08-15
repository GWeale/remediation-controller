"""Minimal async client for the Devin v3 API."""

from typing import Any

import httpx

from .config import Settings

# Statuses reported by GET /v3/organizations/{org_id}/sessions/{devin_id}.
# `suspended` is terminal too: Devin stops working and will not resume on its own.
TERMINAL_STATUSES = {"exit", "error", "suspended"}
FAILURE_STATUSES = {"error"}


class DevinClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._settings = settings
        self._base = settings.devin_api_base.rstrip("/")
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=30, transport=self._transport)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.devin_api_key}",
            "Content-Type": "application/json",
        }

    @property
    def _sessions_url(self) -> str:
        return f"{self._base}/v3/organizations/{self._settings.devin_org_id}/sessions"

    async def create_session(
        self, prompt: str, title: str, tags: list[str], repo: str, issue_url: str
    ) -> dict[str, Any]:
        async with self._client() as client:
            resp = await client.post(
                self._sessions_url,
                headers=self._headers(),
                json={
                    "prompt": prompt,
                    "title": title,
                    "tags": tags,
                    "repos": [repo],
                    "session_links": [issue_url],
                    "max_acu_limit": 3,
                    "bypass_approval": True,
                    "structured_output_required": False,
                    "resumable": True,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def get_session(self, session_id: str) -> dict[str, Any]:
        async with self._client() as client:
            resp = await client.get(
                f"{self._sessions_url}/{session_id}", headers=self._headers()
            )
            resp.raise_for_status()
            return resp.json()


def build_prompt(repo: str, issue_number: int, issue_title: str, issue_url: str) -> str:
    return (
        f"Remediate GitHub issue #{issue_number} in the fork {repo}.\n\n"
        f"Issue title: {issue_title}\n"
        f"Issue URL: {issue_url}\n\n"
        "Instructions:\n"
        f"1. Read the issue and reproduce the problem in {repo}.\n"
        "2. Implement a minimal, well-tested fix on a new branch.\n"
        "3. Run the relevant lint and test commands.\n"
        f"4. Open a pull request against {repo} (the fork) that references the issue.\n\n"
        "Constraints:\n"
        "- NEVER merge pull requests.\n"
        "- NEVER push to or open pull requests against apache/superset upstream; "
        f"work only within the {repo} fork.\n"
    )
