"""Remediation controller: GitHub webhook -> Devin session -> dashboard."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from . import db
from .config import get_settings
from .devin_client import DevinClient, build_prompt
from .monitor import monitor_loop
from .webhook import extract_labeled_issue, verify_signature

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.conn = db.connect(settings.database_path)
    app.state.devin = DevinClient(settings)
    task = asyncio.create_task(
        monitor_loop(app.state.conn, app.state.devin, settings.poll_interval_seconds)
    )
    try:
        yield
    finally:
        task.cancel()
        app.state.conn.close()


app = FastAPI(title="remediation-controller", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str = Header(default=""),
):
    settings = request.app.state.settings
    body = await request.body()
    if not verify_signature(settings.github_webhook_secret, body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="invalid signature")

    payload = json.loads(body)
    issue = extract_labeled_issue(
        x_github_event, payload, settings.target_repo, settings.trigger_label
    )
    if issue is None:
        return {"status": "ignored"}

    conn = request.app.state.conn
    run_id = db.create_run(conn, **issue)
    if run_id is None:
        return {"status": "duplicate", "detail": "run already exists for this issue"}

    try:
        session = await request.app.state.devin.create_session(
            prompt=build_prompt(
                issue["repo"],
                issue["issue_number"],
                issue["issue_title"],
                issue["issue_url"],
            ),
            title=f"Remediate {issue['repo']}#{issue['issue_number']}",
            tags=[
                "remediation-controller",
                f"issue-{issue['issue_number']}",
            ],
            repo=issue["repo"],
            issue_url=issue["issue_url"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to create Devin session")
        db.update_run(conn, run_id, status="failed", error=str(exc))
        raise HTTPException(status_code=502, detail="failed to create Devin session")

    db.update_run(
        conn,
        run_id,
        status="session_created",
        devin_session_id=session.get("session_id"),
        devin_session_url=session.get("url"),
    )
    return {
        "status": "created",
        "run_id": run_id,
        "devin_session_id": session.get("session_id"),
        "devin_session_url": session.get("url"),
    }


def _run_to_dict(run) -> dict:
    d = dict(run)
    d["pull_requests"] = json.loads(run["pull_requests"] or "[]")
    return d


@app.get("/api/runs")
async def api_runs(request: Request) -> list[dict]:
    return [_run_to_dict(r) for r in db.list_runs(request.app.state.conn)]


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    runs = [_run_to_dict(r) for r in db.list_runs(request.app.state.conn)]
    stats = {
        "total": len(runs),
        "failed": sum(1 for r in runs if r["status"] == "failed"),
        "active": sum(
            1 for r in runs if r["status"] in ("pending", "session_created", "running")
        ),
        "completed": sum(1 for r in runs if r["status"] == "completed"),
    }
    return templates.TemplateResponse(
        request, "dashboard.html", {"runs": runs, "stats": stats}
    )
