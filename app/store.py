"""Crash-resilient SQLite persistence with safe journaling, transactions and migrations.

The JSON snapshots from v0.1-v0.3 are imported once when found. Runtime state is
stored in one local database so concurrent requests cannot overwrite each other's
pending actions or run history.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .sqlite_safety import open_database


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent
        raw = Path(os.getenv("INDRA_DATA_DIR", "./data")).expanduser()
        self.root = (raw if raw.is_absolute() else project_root / raw).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "indra.sqlite3"
        # Legacy paths are retained solely for a one-time, backwards-compatible import.
        self.events_path = self.root / "events.jsonl"
        self.actions_path = self.root / "pending_actions.json"
        self.runs_path = self.root / "runs.json"
        self.lock = threading.RLock()
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
                CREATE TABLE IF NOT EXISTS actions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_actions_created ON actions(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    title TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);
                CREATE TABLE IF NOT EXISTS run_feedback (
                    run_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                    rating TEXT NOT NULL CHECK(rating IN ('useful','incorrect','incomplete','risky')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_run_feedback_updated ON run_feedback(updated_at DESC);
                """
            )
        self._migrate_legacy_files()

    def _connect(self) -> sqlite3.Connection:
        conn = open_database(self.db_path, timeout=8.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=8000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    def _migrate_legacy_files(self) -> None:
        with self.lock, self._connection() as conn:
            migrated = conn.execute("SELECT value FROM metadata WHERE key='legacy_json_migrated'").fetchone()
            if migrated:
                return
            # Import only if the corresponding SQLite table is empty. Existing databases win.
            if self.runs_path.exists() and not conn.execute("SELECT 1 FROM runs LIMIT 1").fetchone():
                try:
                    rows = json.loads(self.runs_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    rows = []
                if isinstance(rows, list):
                    for row in rows[:500]:
                        if not isinstance(row, dict) or not row.get("run_id"):
                            continue
                        created = str(row.get("created_at") or now())
                        conn.execute("INSERT OR IGNORE INTO runs(run_id,created_at,status,payload) VALUES(?,?,?,?)",
                                     (str(row["run_id"]), created, str(row.get("status", "unknown")), self._json(row)))
            if self.actions_path.exists() and not conn.execute("SELECT 1 FROM actions LIMIT 1").fetchone():
                try:
                    rows = json.loads(self.actions_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    rows = []
                if isinstance(rows, list):
                    for row in rows[:2000]:
                        if not isinstance(row, dict) or not row.get("id"):
                            continue
                        created = str(row.get("created_at") or now())
                        conn.execute("INSERT OR IGNORE INTO actions(id,created_at,status,payload) VALUES(?,?,?,?)",
                                     (str(row["id"]), created, str(row.get("status", "pending")), self._json(row)))
            if self.events_path.exists() and not conn.execute("SELECT 1 FROM events LIMIT 1").fetchone():
                try:
                    with self.events_path.open("r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                row = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if not isinstance(row, dict):
                                continue
                            event_id = str(row.get("event_id") or uuid.uuid4().hex)
                            timestamp = str(row.get("timestamp") or now())
                            kind = str(row.get("type") or "legacy_event")
                            conn.execute("INSERT OR IGNORE INTO events(event_id,timestamp,type,payload) VALUES(?,?,?,?)",
                                         (event_id, timestamp, kind, self._json(row)))
                except OSError:
                    pass
            conn.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('legacy_json_migrated','1')")

    def event(self, kind: str, **fields: Any) -> dict[str, Any]:
        row = {"event_id": uuid.uuid4().hex, "timestamp": now(), "type": kind, **fields}
        with self.lock, self._connection() as conn:
            conn.execute("INSERT INTO events(event_id,timestamp,type,payload) VALUES(?,?,?,?)",
                         (row["event_id"], row["timestamp"], kind, self._json(row)))
            # Bound local telemetry growth while retaining a substantial recent audit window.
            count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            if count > 50000:
                conn.execute("DELETE FROM events WHERE seq IN (SELECT seq FROM events ORDER BY seq ASC LIMIT ?)",
                             (count - 40000,))
        return row

    def list_events(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._connection() as conn:
            rows = conn.execute("SELECT payload FROM events ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def list_runs(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT payload FROM runs ORDER BY created_at DESC LIMIT 200").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def save_run(self, run: dict[str, Any]) -> None:
        run_id = str(run.get("run_id") or uuid.uuid4().hex)
        created = str(run.get("created_at") or now())
        status = str(run.get("status") or "unknown")
        payload = self._json({**run, "run_id": run_id, "created_at": created, "status": status})
        with self.lock, self._connection() as conn:
            conn.execute("INSERT INTO runs(run_id,created_at,status,payload) VALUES(?,?,?,?) "
                         "ON CONFLICT(run_id) DO UPDATE SET created_at=excluded.created_at,status=excluded.status,payload=excluded.payload",
                         (run_id, created, status, payload))
            conn.execute("DELETE FROM runs WHERE run_id IN (SELECT run_id FROM runs ORDER BY created_at DESC LIMIT -1 OFFSET 200)")

    def list_actions(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT payload FROM actions ORDER BY created_at DESC LIMIT 2000").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def add_action(self, action: dict[str, Any]) -> dict[str, Any]:
        created_at = now()
        row = {"id": uuid.uuid4().hex, "created_at": created_at, "status": "pending", **action}
        with self.lock, self._connection() as conn:
            conn.execute("INSERT INTO actions(id,created_at,status,payload) VALUES(?,?,?,?)",
                         (row["id"], created_at, row["status"], self._json(row)))
            conn.execute("DELETE FROM actions WHERE id IN (SELECT id FROM actions WHERE status NOT IN ('pending','applying') ORDER BY created_at DESC LIMIT -1 OFFSET 1000)")
        self.event("action_proposed", action_id=row["id"], path=row.get("path"))
        return row

    def claim_action(self, action_id: str) -> dict[str, Any] | None:
        """Atomically change pending -> applying across concurrent requests/processes."""
        found = None
        with self.lock, self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                result = conn.execute("SELECT payload FROM actions WHERE id=? AND status='pending'", (action_id,)).fetchone()
                if result:
                    found = json.loads(result["payload"])
                    found["status"] = "applying"
                    found["updated_at"] = now()
                    cursor = conn.execute("UPDATE actions SET status='applying',payload=? WHERE id=? AND status='pending'",
                                          (self._json(found), action_id))
                    if cursor.rowcount != 1:
                        found = None
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        if found:
            self.event("action_status_changed", action_id=action_id, status="applying")
        return found

    def update_action(self, action_id: str, status: str, **fields: Any) -> dict[str, Any] | None:
        updated = None
        with self.lock, self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                result = conn.execute("SELECT payload FROM actions WHERE id=?", (action_id,)).fetchone()
                if result:
                    updated = json.loads(result["payload"])
                    updated.update(fields)
                    updated["status"] = status
                    updated["updated_at"] = now()
                    conn.execute("UPDATE actions SET status=?,payload=? WHERE id=?",
                                 (status, self._json(updated), action_id))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        if updated:
            self.event("action_status_changed", action_id=action_id, status=status)
        return updated

    FEEDBACK_RATINGS = ("useful", "incorrect", "incomplete", "risky")

    def set_run_feedback(self, run_id: str, conversation_id: str, rating: str) -> dict[str, Any]:
        """Store one explicit, content-free rating per run; never stores answer text or free-form comments."""
        if rating not in self.FEEDBACK_RATINGS:
            raise ValueError("Unsupported feedback rating.")
        timestamp = now()
        with self.lock, self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                exists = conn.execute(
                    "SELECT 1 FROM conversations WHERE conversation_id=?", (conversation_id,)
                ).fetchone()
                if not exists:
                    conn.rollback()
                    raise ValueError("Saved conversation not found.")
                conn.execute(
                    "INSERT INTO run_feedback(run_id,conversation_id,rating,created_at,updated_at) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(run_id) DO UPDATE SET conversation_id=excluded.conversation_id, "
                    "rating=excluded.rating, updated_at=excluded.updated_at",
                    (run_id, conversation_id, rating, timestamp, timestamp),
                )
                # Keep bounded local telemetry. One rating per run makes this limit meaningful.
                conn.execute(
                    "DELETE FROM run_feedback WHERE run_id IN "
                    "(SELECT run_id FROM run_feedback ORDER BY updated_at DESC LIMIT -1 OFFSET 5000)"
                )
                conn.commit()
            except Exception:
                if conn.in_transaction:
                    conn.rollback()
                raise
        return {"run_id": run_id, "conversation_id": conversation_id, "rating": rating, "updated_at": timestamp}

    def feedback_summary(self, conversation_id: str | None = None) -> dict[str, Any]:
        """Aggregate local ratings; expose per-run labels only for an explicitly selected conversation."""
        with self._connection() as conn:
            grouped = conn.execute(
                "SELECT rating, COUNT(*) AS n FROM run_feedback GROUP BY rating"
            ).fetchall()
            if conversation_id:
                rows = conn.execute(
                    "SELECT run_id, rating FROM run_feedback WHERE conversation_id=? ORDER BY updated_at DESC",
                    (conversation_id,),
                ).fetchall()
            else:
                rows = []
        counts = {rating: 0 for rating in self.FEEDBACK_RATINGS}
        for row in grouped:
            if row["rating"] in counts:
                counts[row["rating"]] = int(row["n"])
        total = sum(counts.values())
        flagged = counts["incorrect"] + counts["incomplete"] + counts["risky"]
        return {
            "total": total,
            "flagged": flagged,
            "counts": counts,
            "by_run": {row["run_id"]: row["rating"] for row in rows},
            "scope": "Explicit user ratings stored locally. Ratings are subjective signals, not an objective model-quality score.",
            "local_only": True,
            "sent_to_model": False,
            "used_for_training": False,
            "automatic_adaptation": False,
        }

    def delete_run_feedback(self, run_id: str, conversation_id: str) -> bool:
        """Remove one rating without deleting its run or conversation."""
        with self.lock, self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM run_feedback WHERE run_id=? AND conversation_id=?",
                (run_id, conversation_id),
            )
        return cursor.rowcount > 0

    def clear_run_feedback(self) -> int:
        with self.lock, self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                count = int(conn.execute("SELECT COUNT(*) FROM run_feedback").fetchone()[0])
                conn.execute("DELETE FROM run_feedback")
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return count

    def create_conversation(self, workspace: str, title: str = "New conversation") -> dict[str, Any]:
        conversation_id = uuid.uuid4().hex
        timestamp = now()
        row = {
            "conversation_id": conversation_id,
            "title": str(title or "New conversation").strip()[:120] or "New conversation",
            "workspace": str(workspace),
            "created_at": timestamp,
            "updated_at": timestamp,
            "messages": [],
        }
        with self.lock, self._connection() as conn:
            conn.execute(
                "INSERT INTO conversations(conversation_id,created_at,updated_at,workspace,title,payload) VALUES(?,?,?,?,?,?)",
                (conversation_id, timestamp, timestamp, row["workspace"], row["title"], self._json(row)),
            )
        self.event("conversation_created", conversation_id=conversation_id, workspace=str(workspace))
        return row

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute("SELECT payload FROM conversations WHERE conversation_id=?", (conversation_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT conversation_id,title,workspace,created_at,updated_at,payload FROM conversations ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        output = []
        for row in rows:
            try:
                payload = json.loads(row["payload"])
            except (TypeError, json.JSONDecodeError):
                payload = {}
            messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
            output.append({
                "conversation_id": row["conversation_id"], "title": row["title"],
                "workspace": row["workspace"], "created_at": row["created_at"],
                "updated_at": row["updated_at"], "message_count": len(messages),
            })
        return output

    def append_conversation_message(
        self, conversation_id: str, role: str, content: str, *, run_id: str | None = None, status: str | None = None
    ) -> dict[str, Any] | None:
        if role not in {"user", "assistant"}:
            raise ValueError("Conversation role must be user or assistant.")
        message = {
            "role": role, "content": str(content)[:12000], "created_at": now(),
        }
        if run_id:
            message["run_id"] = str(run_id)[:128]
        if status:
            message["status"] = str(status)[:40]
        with self.lock, self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                found = conn.execute("SELECT payload FROM conversations WHERE conversation_id=?", (conversation_id,)).fetchone()
                if not found:
                    conn.rollback()
                    return None
                row = json.loads(found["payload"])
                messages = row.get("messages") if isinstance(row.get("messages"), list) else []
                messages.append(message)
                messages = messages[-80:]
                # Bound saved conversation text to keep the local database predictable.
                while messages and sum(len(str(item.get("content", ""))) for item in messages) > 120000:
                    messages.pop(0)
                row["messages"] = messages
                if role == "user" and row.get("title") == "New conversation":
                    title = " ".join(message["content"].split())
                    row["title"] = (title[:77] + "…") if len(title) > 78 else (title or "New conversation")
                row["updated_at"] = message["created_at"]
                conn.execute(
                    "UPDATE conversations SET updated_at=?,title=?,payload=? WHERE conversation_id=?",
                    (row["updated_at"], row["title"], self._json(row), conversation_id),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return row

    def rename_conversation(self, conversation_id: str, title: str) -> dict[str, Any] | None:
        clean_title = " ".join(str(title).split())[:120]
        if not clean_title:
            raise ValueError("Conversation title cannot be empty.")
        with self.lock, self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                found = conn.execute("SELECT payload FROM conversations WHERE conversation_id=?", (conversation_id,)).fetchone()
                if not found:
                    conn.rollback()
                    return None
                row = json.loads(found["payload"])
                row["title"] = clean_title
                row["updated_at"] = now()
                conn.execute("UPDATE conversations SET title=?,updated_at=?,payload=? WHERE conversation_id=?",
                             (clean_title, row["updated_at"], self._json(row), conversation_id))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return row

    def delete_conversation(self, conversation_id: str) -> bool:
        with self.lock, self._connection() as conn:
            cursor = conn.execute("DELETE FROM conversations WHERE conversation_id=?", (conversation_id,))
        if cursor.rowcount:
            self.event("conversation_deleted", conversation_id=conversation_id)
            return True
        return False

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._connection() as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key=?", ("setting:" + key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (TypeError, json.JSONDecodeError):
            return default

    def set_setting(self, key: str, value: Any) -> None:
        encoded = self._json(value)
        with self.lock, self._connection() as conn:
            conn.execute("INSERT INTO metadata(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                         ("setting:" + key, encoded))
