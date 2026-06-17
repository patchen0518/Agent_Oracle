"""SQLite-backed session history storage."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

DB_PATH = Path.home() / ".oracle" / "history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY,
    name       TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
    id             INTEGER PRIMARY KEY,
    session_id     INTEGER REFERENCES sessions(id),
    role           TEXT NOT NULL,
    content        TEXT,
    tool_call_data TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS turn_outcomes (
    id                  INTEGER PRIMARY KEY,
    session_id          INTEGER REFERENCES sessions(id),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    original_message    TEXT NOT NULL,
    iterations_used     INTEGER NOT NULL,
    hit_iteration_limit BOOLEAN NOT NULL DEFAULT 0,
    tool_errors_count   INTEGER NOT NULL DEFAULT 0,
    tool_errors_summary TEXT,
    completion_check_result TEXT,
    verify_verdict      TEXT,
    verify_text         TEXT,
    modified_paths      TEXT,
    tags                TEXT
);
CREATE TABLE IF NOT EXISTS rejected_proposals (
    id              INTEGER PRIMARY KEY,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    target_path     TEXT NOT NULL,
    action          TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    rationale       TEXT,
    rejected_at     TIMESTAMP
);
"""


class HistoryDB:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def create_session(self, session_id: str) -> int:
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO sessions (name) VALUES (?)", (session_id,)
        )
        self._conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = self._conn.execute("SELECT id FROM sessions WHERE name=?", (session_id,)).fetchone()
        return row["id"]

    def append_message(self, session_db_id: int, role: str, content: str | None, tool_call_data: dict | None = None) -> None:
        self._conn.execute(
            "INSERT INTO messages (session_id, role, content, tool_call_data) VALUES (?,?,?,?)",
            (session_db_id, role, content, json.dumps(tool_call_data) if tool_call_data else None),
        )
        self._conn.commit()

    def get_messages(self, session_db_id: int, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT role, content, tool_call_data FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_db_id, limit),
        ).fetchall()
        result = []
        for r in reversed(rows):
            msg: dict = {"role": r["role"]}
            if r["content"] is not None:
                msg["content"] = r["content"]
            if r["tool_call_data"]:
                msg["tool_calls"] = json.loads(r["tool_call_data"])
            result.append(msg)
        return result

    # --- Phase 11 outcome tracking ---

    def record_outcome(self, session_db_id: int, data: dict) -> int:
        cur = self._conn.execute(
            """INSERT INTO turn_outcomes
               (session_id, original_message, iterations_used, hit_iteration_limit,
                tool_errors_count, tool_errors_summary, completion_check_result, modified_paths, tags)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                session_db_id,
                data.get("original_message", ""),
                data.get("iterations_used", 0),
                1 if data.get("hit_iteration_limit") else 0,
                data.get("tool_errors_count", 0),
                json.dumps(data.get("tool_errors_summary")) if data.get("tool_errors_summary") else None,
                data.get("completion_check_result"),
                json.dumps(list(data.get("modified_paths", []))) if data.get("modified_paths") else None,
                json.dumps(data.get("tags", [])),
            ),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def attach_verify_verdict(self, outcome_id: int, verdict: str, text: str) -> None:
        self._conn.execute(
            "UPDATE turn_outcomes SET verify_verdict=?, verify_text=? WHERE id=?",
            (verdict, text, outcome_id),
        )
        self._conn.commit()

    def query_outcomes(self, limit: int = 20, days: int = 30, verdict_filter: str | None = None) -> list[dict]:
        q = "SELECT * FROM turn_outcomes WHERE created_at >= datetime('now', ?) ORDER BY id DESC LIMIT ?"
        rows = self._conn.execute(q, (f"-{days} days", limit)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if verdict_filter and d.get("verify_verdict") != verdict_filter:
                continue
            result.append(d)
        return result

    def count_outcomes(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM turn_outcomes").fetchone()
        return row[0]

    def record_rejected_proposal(self, target_path: str, action: str, content_hash: str, rationale: str | None = None) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO rejected_proposals (target_path, action, content_hash, rationale, rejected_at) VALUES (?,?,?,?,datetime('now'))",
            (target_path, action, content_hash, rationale),
        )
        self._conn.commit()

    def query_rejected_proposals(self, days: int = 30) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM rejected_proposals WHERE rejected_at >= datetime('now', ?) ORDER BY id DESC",
            (f"-{days} days",),
        ).fetchall()
        return [dict(r) for r in rows]
