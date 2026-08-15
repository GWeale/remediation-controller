# remediation-controller

A small FastAPI service that turns labeled GitHub issues into Devin remediation
sessions and tracks them on a dashboard.

Flow: an issue in **GWeale/superset** is labeled **`devin:ready`** → GitHub
sends a webhook → the controller verifies the signature, records a run in
SQLite, and creates a **Devin v3 API** session prompting Devin to fix the issue
and open a PR against the fork. A background poller keeps each run's session
status and pull requests up to date, and `/` serves a status dashboard.

Safety: the Devin prompt explicitly forbids merging pull requests or touching
`apache/superset` upstream; all work stays inside the fork. The controller
itself never calls the GitHub write API at all.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # fill in DEVIN_API_KEY, DEVIN_ORG_ID, GITHUB_WEBHOOK_SECRET
uvicorn app.main:app --reload
```

- Dashboard: http://localhost:8000/
- Health: `GET /health`
- Runs as JSON: `GET /api/runs`
- Webhook receiver: `POST /webhook/github`

### Docker

```bash
docker build -t remediation-controller .
docker run --env-file .env -p 8000:8000 -v remediation-data:/data remediation-controller
```

## GitHub webhook setup

1. In `GWeale/superset` → Settings → Webhooks → Add webhook.
2. Payload URL: `https://<your-host>/webhook/github` (use e.g. `ngrok http 8000`
   for local demos).
3. Content type: `application/json`.
4. Secret: the same value as `GITHUB_WEBHOOK_SECRET`.
5. Events: select individual events → **Issues** only.

Then create/choose an issue and add the `devin:ready` label. The controller
ignores every event except `issues.labeled` with the configured label on the
configured repo, and it deduplicates by `(repo, issue_number)` so re-labeling
never spawns a second session.

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Purpose | Default |
| --- | --- | --- |
| `DEVIN_API_KEY` | Devin API bearer token | required |
| `DEVIN_ORG_ID` | Devin organization id (`org-...`) | required |
| `DEVIN_API_BASE` | Devin API base URL | `https://api.devin.ai` |
| `GITHUB_WEBHOOK_SECRET` | HMAC secret for `X-Hub-Signature-256` | required |
| `TARGET_REPO` | Repo whose issues trigger runs | `GWeale/superset` |
| `TRIGGER_LABEL` | Label that triggers a run | `devin:ready` |
| `DATABASE_PATH` | SQLite file | `runs.db` |
| `POLL_INTERVAL_SECONDS` | Session poll cadence | `30` |

## How it works

- `app/webhook.py` — verifies `X-Hub-Signature-256` (HMAC-SHA256,
  constant-time compare) and filters events down to
  `issues.labeled` + matching repo + matching label.
- `app/devin_client.py` — thin async client for the Devin v3 API
  (`POST/GET /v3/organizations/{org_id}/sessions`), plus the remediation
  prompt template.
- `app/db.py` — SQLite schema and helpers. Run lifecycle:
  `pending → session_created → running → completed | failed`.
- `app/monitor.py` — asyncio background loop polling active sessions and
  capturing their pull requests. Status mapping: `error → failed` (with
  `status_detail` stored as the run error), `exit → completed`, `suspended`
  (also terminal) → `completed` when the session produced at least one pull
  request, otherwise `failed` with `status_detail` as the error; anything else
  → `running`.
- `app/main.py` — FastAPI wiring: webhook endpoint, JSON API, HTML dashboard.

## Tests

```bash
pytest
```

Covers signature verification (valid/invalid/tampered/missing), event
filtering, run creation with a mocked Devin client, duplicate suppression,
failure handling, retry-on-relabel, the exact Devin v3 request path and body
(via `httpx.MockTransport`), dashboard rendering, and monitor status
transitions including suspended sessions with and without pull requests.

## Scope notes

- Single-process SQLite + in-process poller: fine for a small deployment;
  would move to a real queue/worker and Postgres at scale.
- The controller trusts Devin to respect the no-merge/fork-only constraints in
  the prompt; a hardened version would also use a GitHub token with
  fork-scoped, non-merge permissions as a hard guarantee.
- No auth on the read-only dashboard.
