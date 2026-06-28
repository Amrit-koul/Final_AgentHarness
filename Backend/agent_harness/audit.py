"""
audit.py: Audit module for the enterprise Agent Harness control plane.
Persists session audit trails to SQLite.
"""
import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

# data/ is at Backend/data/audit.db
DB_PATH = Path(__file__).parent.parent / "data" / "audit.db"

class AuditStore:
    _instance = None
    _singleton_lock = Lock()

    def __new__(cls):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._db_lock = Lock()
        self._create_tables()

    def _create_tables(self):
        with self._db_lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS audit_sessions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    query       TEXT NOT NULL,
                    intent      TEXT DEFAULT 'UNKNOWN',
                    final_resp  TEXT,
                    step_count  INTEGER DEFAULT 0,
                    total_ms    INTEGER DEFAULT 0,
                    timestamp   TEXT DEFAULT (datetime('now')),
                    audit_trail TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_session_id ON audit_sessions(session_id);
                CREATE INDEX IF NOT EXISTS idx_timestamp  ON audit_sessions(timestamp);

                CREATE TABLE IF NOT EXISTS guardrail_events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT,
                    event_type  TEXT NOT NULL,
                    detail      TEXT,
                    timestamp   TEXT DEFAULT (datetime('now'))
                );
            """)
            self._conn.commit()

    def save_session(self, session_id: str, query: str, intent: str,
                     final_resp: str, audit_trail: list, total_ms: int):
        try:
            step_count = len(audit_trail)
            trail_json = json.dumps(audit_trail)
            with self._db_lock:
                self._conn.execute(
                    """INSERT INTO audit_sessions
                       (session_id, query, intent, final_resp, step_count, total_ms, audit_trail)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, query, intent or "UNKNOWN", final_resp,
                     step_count, total_ms, trail_json),
                )
                self._conn.commit()
        except Exception:
            logging.exception("AuditStore.save_session failed silently")

    def save_guardrail_event(self, session_id: str, event_type: str, detail: str):
        try:
            with self._db_lock:
                self._conn.execute(
                    "INSERT INTO guardrail_events (session_id, event_type, detail) VALUES (?, ?, ?)",
                    (session_id, event_type, detail),
                )
                self._conn.commit()
        except Exception:
            logging.exception("AuditStore.save_guardrail_event failed silently")

    def get_sessions(self, limit: int = 50, offset: int = 0) -> list:
        try:
            with self._db_lock:
                cursor = self._conn.execute(
                    """SELECT id, session_id, query, intent, step_count, total_ms, timestamp
                       FROM audit_sessions
                       ORDER BY id DESC
                       LIMIT ? OFFSET ?""",
                    (limit, offset),
                )
                rows = cursor.fetchall()
            return [
                {
                    "id": r[0], "session_id": r[1], "query": r[2],
                    "intent": r[3], "step_count": r[4],
                    "total_ms": r[5], "timestamp": r[6],
                }
                for r in rows
            ]
        except Exception:
            logging.exception("AuditStore.get_sessions failed")
            return []

    def get_session(self, session_id: str) -> Optional[dict]:
        try:
            with self._db_lock:
                cursor = self._conn.execute(
                    """SELECT id, session_id, query, intent, final_resp,
                              step_count, total_ms, timestamp, audit_trail
                       FROM audit_sessions
                       WHERE session_id = ?
                       ORDER BY id DESC LIMIT 1""",
                    (session_id,),
                )
                row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0], "session_id": row[1], "query": row[2],
                "intent": row[3], "final_resp": row[4],
                "step_count": row[5], "total_ms": row[6],
                "timestamp": row[7],
                "audit_trail": json.loads(row[8]) if row[8] else [],
            }
        except Exception:
            logging.exception("AuditStore.get_session failed")
            return None

    def get_guardrail_events(self, limit: int = 100) -> list:
        try:
            with self._db_lock:
                cursor = self._conn.execute(
                    """SELECT id, session_id, event_type, detail, timestamp
                       FROM guardrail_events
                       ORDER BY id DESC LIMIT ?""",
                    (limit,),
                )
                rows = cursor.fetchall()
            return [
                {
                    "id": r[0], "session_id": r[1],
                    "event_type": r[2], "detail": r[3], "timestamp": r[4],
                }
                for r in rows
            ]
        except Exception:
            logging.exception("AuditStore.get_guardrail_events failed")
            return []

    def get_stats(self) -> dict:
        try:
            with self._db_lock:
                cursor = self._conn.execute(
                    "SELECT COUNT(*), AVG(step_count), AVG(total_ms) FROM audit_sessions"
                )
                row = cursor.fetchone()
                total = row[0] or 0
                avg_steps = round(row[1] or 0, 1)
                avg_latency = round(row[2] or 0)

                cursor2 = self._conn.execute(
                    "SELECT intent, COUNT(*) FROM audit_sessions GROUP BY intent"
                )
                intent_rows = cursor2.fetchall()
            intent_breakdown = {r[0]: r[1] for r in intent_rows}
            return {
                "total_sessions": total,
                "avg_steps": avg_steps,
                "avg_latency_ms": avg_latency,
                "intent_breakdown": intent_breakdown,
            }
        except Exception:
            logging.exception("AuditStore.get_stats failed")
            return {"total_sessions": 0, "avg_steps": 0, "avg_latency_ms": 0, "intent_breakdown": {}}


audit_store = AuditStore()
