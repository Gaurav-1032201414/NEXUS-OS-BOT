"""
core/memory.py
Persistent conversation memory backed by SQLite.
Stores turns, system facts, and user preferences. Survives restarts.
"""
import sqlite3
import json
import time
import threading
import logging
from pathlib import Path
import os

logger = logging.getLogger("nexus.memory")


class Memory:
    """
    Thread-safe SQLite-backed memory.
    Tables:
      turns       — full conversation history (role, content, ts)
      facts       — key/value system facts the agent learns
      preferences — user preferences
    """

    def __init__(self, db_path: str = "~/.nexus/memory.db", max_turns: int = 20):
        self.db_path  = Path(os.path.expanduser(db_path))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_turns = max_turns
        self._lock = threading.Lock()
        # check_same_thread=False because FastAPI/uvicorn use multiple threads;
        # we serialize all access with our own lock.
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS turns (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    session TEXT    NOT NULL DEFAULT 'default',
                    role    TEXT    NOT NULL,
                    content TEXT    NOT NULL,
                    ts      REAL    NOT NULL
                );
                CREATE TABLE IF NOT EXISTS facts (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    ts    REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session, id);
            """)
            self._conn.commit()

    # ── Conversation turns ──────────────────────────

    def save_turn(self, role: str, content: str, session: str = "default"):
        with self._lock:
            self._conn.execute(
                "INSERT INTO turns(session, role, content, ts) VALUES (?,?,?,?)",
                (session, role, content, time.time())
            )
            self._conn.commit()

    def save_exchange(self, user_msg: str, assistant_msg: str, session: str = "default"):
        with self._lock:
            now = time.time()
            self._conn.executemany(
                "INSERT INTO turns(session, role, content, ts) VALUES (?,?,?,?)",
                [(session, "user", user_msg, now),
                 (session, "assistant", assistant_msg, now)]
            )
            self._conn.commit()

    def recent_turns(self, n: int = None, session: str = "default") -> list[dict]:
        """Return the last n exchanges as a list of {role, content} dicts (chronological)."""
        n = n or self.max_turns
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content FROM turns WHERE session=? ORDER BY id DESC LIMIT ?",
                (session, n * 2)
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def clear_session(self, session: str = "default"):
        with self._lock:
            self._conn.execute("DELETE FROM turns WHERE session=?", (session,))
            self._conn.commit()

    # ── Facts (things the agent learns about the system) ──

    def set_fact(self, key: str, value):
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO facts(key, value, ts) VALUES (?,?,?)",
                (key, json.dumps(value), time.time())
            )
            self._conn.commit()

    def get_fact(self, key: str, default=None):
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM facts WHERE key=?", (key,)
            ).fetchone()
        return json.loads(row["value"]) if row else default

    def all_facts(self) -> dict:
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM facts").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    # ── User preferences ──────────────────────────────

    def set_preference(self, key: str, value: str):
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO preferences(key, value) VALUES (?,?)",
                (key, str(value))
            )
            self._conn.commit()

    def get_preference(self, key: str, default=None):
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM preferences WHERE key=?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def close(self):
        with self._lock:
            self._conn.close()
