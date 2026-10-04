"""SQLite store for decisions, snapshots and framework versions. PRD 52, 53, 62, 64.

PRD 53 is the reason this exists. Every evaluation is frozen at the moment of the
decision. If Apple rises 25 percent next month, the application must not rewrite the
reasoning that was recorded today. That is what makes the Trading Notes authentic and
what stops hindsight bias from creeping into the committee record.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[1] / "cashcows.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    role TEXT NOT NULL,
    framework_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT,
    security_quality REAL, laura_fit REAL, composite REAL, data_confidence REAL,
    red_gate TEXT, signal TEXT,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER REFERENCES snapshots(id),
    created_at TEXT NOT NULL,
    author TEXT NOT NULL,
    portfolio TEXT NOT NULL,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    position TEXT,
    reason TEXT,
    evidence TEXT,
    client_link TEXT,
    risk TEXT,
    review_date TEXT,
    outcome TEXT,
    override INTEGER DEFAULT 0,
    override_reason TEXT,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS framework_versions (
    version TEXT PRIMARY KEY,
    author TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    manifest TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_ticker ON snapshots(ticker);
CREATE INDEX IF NOT EXISTS idx_decisions_ticker ON decisions(ticker);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def record_snapshot(result: dict, created_by: str = "") -> int:
    """Freeze one evaluation exactly as it was computed."""
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO snapshots
               (ticker, role, framework_version, created_at, created_by,
                security_quality, laura_fit, composite, data_confidence, red_gate, signal, payload)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                result["ticker"], result["role"], result["framework_version"], _now(), created_by,
                result["scores"]["security_quality"], result["scores"]["laura_fit"],
                result["scores"]["composite"], result["scores"]["data_confidence"],
                result["red_gate"]["status"], result["signal"]["signal"],
                json.dumps(result, default=str),
            ),
        )
        return int(cur.lastrowid)


def snapshot_history(ticker: str, limit: int = 25) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, ticker, role, framework_version, created_at, created_by,
                      security_quality, laura_fit, composite, data_confidence, red_gate, signal
               FROM snapshots WHERE ticker = ? ORDER BY id DESC LIMIT ?""",
            (ticker.upper(), limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_snapshot(snapshot_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT payload FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        return json.loads(row["payload"]) if row else None


def record_decision(entry: dict, snapshot_id: int | None = None, portfolio: str = "competition",
                    override: bool = False, override_reason: str = "") -> int:
    """PRD 64. An override is permanently recorded, never silently applied."""
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO decisions
               (snapshot_id, created_at, author, portfolio, ticker, action, position, reason,
                evidence, client_link, risk, review_date, outcome, override, override_reason, payload)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                snapshot_id, _now(), entry.get("author", ""), portfolio, entry["security"].split()[0],
                entry.get("action", "EVALUATE"), entry.get("position", ""), entry.get("reason", ""),
                json.dumps(entry.get("evidence", [])), entry.get("client_link", ""),
                entry.get("risk", ""), entry.get("review_date", ""), entry.get("outcome", ""),
                1 if override else 0, override_reason,
                json.dumps(entry, default=str),
            ),
        )
        return int(cur.lastrowid)


def list_decisions(limit: int = 100, portfolio: str | None = None) -> list[dict]:
    query = "SELECT * FROM decisions"
    params: list[Any] = []
    if portfolio:
        query += " WHERE portfolio = ?"
        params.append(portfolio)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d["payload"])
            d["evidence"] = json.loads(d["evidence"] or "[]")
            out.append(d)
        return out


def record_framework_version(manifest: dict) -> None:
    """PRD 62. A weight change creates a new version and triggers a rescore."""
    with connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO framework_versions (version, author, created_at, reason, manifest)
               VALUES (?,?,?,?,?)""",
            (manifest["version"], manifest["author"], _now(), manifest["reason"],
             json.dumps(manifest, default=str)),
        )


def list_framework_versions() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT version, author, created_at, reason FROM framework_versions ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def stale_snapshots(current_version: str) -> list[dict]:
    """Evaluations scored under an older framework version, which PRD 62 says must be rescored."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT ticker, role, framework_version, MAX(created_at) AS last_scored
               FROM snapshots WHERE framework_version != ?
               GROUP BY ticker, role, framework_version""",
            (current_version,),
        ).fetchall()
        return [dict(r) for r in rows]
