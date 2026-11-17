"""SQLite review queue.

The original email is stored here, unmasked, because the human agent needs it to
reply. That makes this file the one place personal data rests: keep the database
on an encrypted disk and out of version control (it is in .gitignore).
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from .schemas import EmailIn, QueueItem, TriageResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    sender TEXT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    result_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    final_reply TEXT,
    review_note TEXT,
    reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
"""
STATUSES = ("pending", "approved", "rejected")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str):
        self.path = path
        with closing(self._conn()) as c, c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _item(row: sqlite3.Row) -> QueueItem:
        return QueueItem(
            id=row["id"], received_at=row["received_at"], sender=row["sender"], subject=row["subject"],
            body=row["body"], result=TriageResult.model_validate_json(row["result_json"]), status=row["status"],
            final_reply=row["final_reply"], review_note=row["review_note"], reviewed_at=row["reviewed_at"],
        )

    def add(self, email: EmailIn, result: TriageResult) -> int:
        with closing(self._conn()) as c, c:
            cur = c.execute(
                "INSERT INTO items (received_at, sender, subject, body, result_json) VALUES (?,?,?,?,?)",
                (_now(), email.sender, email.subject, email.body, result.model_dump_json()),
            )
            return int(cur.lastrowid)

    def get(self, item_id: int) -> QueueItem | None:
        with closing(self._conn()) as c:
            row = c.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return self._item(row) if row else None

    def list(self, status: str | None = None, limit: int = 100) -> list[QueueItem]:
        sql, args = "SELECT * FROM items", []
        if status:
            sql += " WHERE status = ?"
            args.append(status)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with closing(self._conn()) as c:
            return [self._item(r) for r in c.execute(sql, args).fetchall()]

    def decide(self, item_id: int, status: str, final_reply: str | None, note: str | None) -> QueueItem | None:
        """Move a pending item to approved/rejected. Returns None if it was not pending."""
        with closing(self._conn()) as c, c:
            cur = c.execute(
                "UPDATE items SET status=?, final_reply=?, review_note=?, reviewed_at=? WHERE id=? AND status='pending'",
                (status, final_reply, note, _now(), item_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get(item_id)

    def stats(self) -> dict:
        with closing(self._conn()) as c:
            by_status = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) n FROM items GROUP BY status")}
            rows = c.execute("SELECT result_json FROM items").fetchall()
        by_category: dict[str, int] = {}
        flagged = 0
        for r in rows:
            res = TriageResult.model_validate_json(r["result_json"])
            by_category[res.category.value] = by_category.get(res.category.value, 0) + 1
            flagged += res.needs_review
        return {"total": len(rows), "by_status": by_status, "by_category": by_category, "flagged_for_review": flagged}
