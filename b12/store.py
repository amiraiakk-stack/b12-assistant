"""SQLite storage for B12 messages and the tasks Claude extracts from them."""

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import date

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,          -- e.g. b12-messages, b12-weekly-plan, b12-newsletter
    title TEXT,
    sent_at TEXT,                  -- as shown by B12, free text
    body TEXT,
    attachment_path TEXT,          -- downloaded PDF/image, if any
    fetched_at TEXT DEFAULT (datetime('now')),
    processed INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL REFERENCES messages(id),
    due_date TEXT,                 -- YYYY-MM-DD, NULL when the message gives no date
    kind TEXT NOT NULL,
    subject TEXT,
    title TEXT NOT NULL,
    details TEXT,
    platform TEXT
);
CREATE INDEX IF NOT EXISTS tasks_due ON tasks(due_date);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def message_id(source: str, title: str, sent_at: str, body: str) -> str:
    return hashlib.sha256(f"{source}|{title}|{sent_at}|{body}".encode()).hexdigest()[:24]


def save_message(source, title, sent_at, body, attachment_path=None, replace_source=False) -> bool:
    """Store a message; returns False when it was already stored.

    With replace_source, a new message replaces every earlier one from the same source
    (used for whole-page snapshots, so a changed page does not duplicate its tasks)."""
    mid = message_id(source, title or "", sent_at or "", body or "")
    with connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO messages (id, source, title, sent_at, body, attachment_path)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (mid, source, title, sent_at, body, attachment_path),
        )
        inserted = cur.rowcount == 1
        if inserted and replace_source:
            old = "SELECT id FROM messages WHERE source = ? AND id != ?"
            conn.execute(f"DELETE FROM tasks WHERE message_id IN ({old})", (source, mid))
            conn.execute(f"DELETE FROM messages WHERE id IN ({old})", (source, mid))
        return inserted


def unprocessed_messages():
    with connect() as conn:
        return conn.execute("SELECT * FROM messages WHERE processed = 0 ORDER BY fetched_at").fetchall()


def save_tasks(msg_id: str, tasks) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM tasks WHERE message_id = ?", (msg_id,))
        conn.executemany(
            "INSERT INTO tasks (message_id, due_date, kind, subject, title, details, platform)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (msg_id, t.due_date, t.kind, t.subject, t.title, t.details, t.platform)
                for t in tasks
            ],
        )
        conn.execute("UPDATE messages SET processed = 1 WHERE id = ?", (msg_id,))


def tasks_between(start: date, end: date):
    with connect() as conn:
        return conn.execute(
            "SELECT t.*, m.source, m.title AS message_title FROM tasks t"
            " JOIN messages m ON m.id = t.message_id"
            " WHERE t.due_date BETWEEN ? AND ? ORDER BY t.due_date, t.subject",
            (start.isoformat(), end.isoformat()),
        ).fetchall()


def recent_undated_tasks(limit: int = 15):
    with connect() as conn:
        return conn.execute(
            "SELECT t.*, m.source, m.title AS message_title FROM tasks t"
            " JOIN messages m ON m.id = t.message_id"
            " WHERE t.due_date IS NULL ORDER BY m.fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
