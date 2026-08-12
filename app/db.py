"""SQLite persistence for remediation runs."""

import sqlite3
import time
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    issue_title TEXT NOT NULL DEFAULT '',
    issue_url TEXT NOT NULL DEFAULT '',
    label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    devin_session_id TEXT,
    devin_session_url TEXT,
    devin_session_status TEXT,
    pull_requests TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_repo_issue
    ON runs (repo, issue_number);
"""

# Run lifecycle: pending -> session_created -> running -> completed | failed


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def create_run(
    conn: sqlite3.Connection,
    repo: str,
    issue_number: int,
    issue_title: str,
    issue_url: str,
    label: str,
) -> Optional[int]:
    """Insert a run; returns the run id, or None if an active/completed one exists.

    A previously failed run for the same issue is reset and reused so that
    re-labeling the issue retries it.
    """
    now = time.time()
    try:
        cur = conn.execute(
            "INSERT INTO runs (repo, issue_number, issue_title, issue_url,"
            " label, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (repo, issue_number, issue_title, issue_url, label, now, now),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        existing = conn.execute(
            "SELECT id, status FROM runs WHERE repo = ? AND issue_number = ?",
            (repo, issue_number),
        ).fetchone()
        if existing and existing["status"] == "failed":
            update_run(
                conn,
                existing["id"],
                status="pending",
                error=None,
                devin_session_id=None,
                devin_session_url=None,
                devin_session_status=None,
                pull_requests="",
                issue_title=issue_title,
                issue_url=issue_url,
                label=label,
            )
            return existing["id"]
        return None


def update_run(conn: sqlite3.Connection, run_id: int, **fields: Any) -> None:
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE runs SET {cols} WHERE id = ?", (*fields.values(), run_id)
    )
    conn.commit()


def get_run(conn: sqlite3.Connection, run_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()


def list_runs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM runs ORDER BY created_at DESC"
    ).fetchall()


def list_active_runs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM runs WHERE status IN ('session_created', 'running')"
    ).fetchall()
