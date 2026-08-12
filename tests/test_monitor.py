import json
from unittest.mock import AsyncMock

import pytest

from app import db
from app.monitor import poll_active_runs


@pytest.fixture()
def conn(tmp_path):
    connection = db.connect(str(tmp_path / "runs.db"))
    yield connection
    connection.close()


def make_run(conn, status="session_created", session_id="devin-1"):
    run_id = db.create_run(conn, "GWeale/superset", 1, "title", "url", "devin:ready")
    db.update_run(conn, run_id, status=status, devin_session_id=session_id)
    return run_id


@pytest.mark.asyncio
async def test_running_session_updates_status_and_prs(conn):
    run_id = make_run(conn)
    client = AsyncMock()
    client.get_session.return_value = {
        "status": "running",
        "pull_requests": [{"pr_url": "https://github.com/GWeale/superset/pull/1", "pr_state": "open"}],
    }
    await poll_active_runs(conn, client)
    run = db.get_run(conn, run_id)
    assert run["status"] == "running"
    assert run["devin_session_status"] == "running"
    assert json.loads(run["pull_requests"]) == [
        {"url": "https://github.com/GWeale/superset/pull/1", "state": "open"}
    ]


@pytest.mark.asyncio
async def test_exit_session_marks_completed(conn):
    run_id = make_run(conn)
    client = AsyncMock()
    client.get_session.return_value = {"status": "exit", "pull_requests": []}
    await poll_active_runs(conn, client)
    assert db.get_run(conn, run_id)["status"] == "completed"


@pytest.mark.asyncio
async def test_error_session_marks_failed(conn):
    run_id = make_run(conn)
    client = AsyncMock()
    client.get_session.return_value = {"status": "error", "pull_requests": []}
    await poll_active_runs(conn, client)
    assert db.get_run(conn, run_id)["status"] == "failed"


@pytest.mark.asyncio
async def test_poll_error_keeps_run_active(conn):
    run_id = make_run(conn)
    client = AsyncMock()
    client.get_session.side_effect = RuntimeError("network")
    await poll_active_runs(conn, client)
    assert db.get_run(conn, run_id)["status"] == "session_created"
