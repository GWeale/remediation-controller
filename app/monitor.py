"""Background polling of active Devin sessions."""

import asyncio
import json
import logging
import sqlite3

from . import db
from .devin_client import FAILURE_STATUSES, TERMINAL_STATUSES, DevinClient

logger = logging.getLogger(__name__)


async def poll_active_runs(conn: sqlite3.Connection, client: DevinClient) -> None:
    """Refresh session status and PRs for every non-terminal run."""
    for run in db.list_active_runs(conn):
        session_id = run["devin_session_id"]
        if not session_id:
            continue
        try:
            session = await client.get_session(session_id)
        except Exception as exc:  # noqa: BLE001 - keep polling other runs
            logger.warning("failed to poll session %s: %s", session_id, exc)
            continue
        status = session.get("status", "")
        pull_requests = session.get("pull_requests") or []
        prs = json.dumps(
            [
                {"url": pr.get("pr_url"), "state": pr.get("pr_state")}
                for pr in pull_requests
            ]
        )
        error = None
        if status in FAILURE_STATUSES:
            run_status = "failed"
            error = session.get("status_detail")
        elif status == "suspended":
            # Suspension is terminal; a session that produced a PR still did its
            # job, one that did not needs attention.
            if pull_requests:
                run_status = "completed"
            else:
                run_status = "failed"
                error = session.get("status_detail") or "suspended"
        elif status in TERMINAL_STATUSES:
            run_status = "completed"
        else:
            run_status = "running"
        db.update_run(
            conn,
            run["id"],
            status=run_status,
            devin_session_status=status,
            pull_requests=prs,
            error=error,
        )


async def monitor_loop(
    conn: sqlite3.Connection, client: DevinClient, interval: int
) -> None:
    while True:
        try:
            await poll_active_runs(conn, client)
        except Exception:  # noqa: BLE001
            logger.exception("monitor tick failed")
        await asyncio.sleep(interval)
