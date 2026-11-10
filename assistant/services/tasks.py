"""The to-do list, as seen by one user.

A task is shared by the household (owner_id NULL) or private (owner_id =
its owner). A private task is invisible AND untouchable for the others:
every query below filters with VISIBLE, even when the id is known.
"""

import sqlite3
from datetime import date

from .users import User

PRIORITIES = ("high", "normal", "low")
MAX_TITLE = 200
# Most important first: CASE turns the word into a number for ORDER BY.
PRIORITY_ORDER = "CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END"
COLUMNS = "id, title, due_date, priority, done, owner_id IS NOT NULL AS private"
VISIBLE = "(owner_id IS NULL OR owner_id = :me)"


def check_priority(priority: str) -> None:
    if priority not in PRIORITIES:
        raise ValueError(f"priority must be one of {PRIORITIES}")


class Tasks:
    def __init__(self, conn: sqlite3.Connection, user: User):
        self.conn = conn
        self.me = user.id

    def add(self, title: str, due_date: str | None, priority: str = "normal",
            private: bool = False) -> dict:
        title = title.strip()
        if not 0 < len(title) <= MAX_TITLE:
            raise ValueError(f"title: 1 to {MAX_TITLE} characters")
        if due_date:
            date.fromisoformat(due_date)  # raises ValueError on a bad date
        check_priority(priority)
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO tasks (title, due_date, priority, owner_id, created_by) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, due_date, priority, self.me if private else None, self.me),
            )
        return self.get(cur.lastrowid)

    def list(self, include_done: bool) -> list[dict]:
        """Most important first, then the closest due date."""
        sql = f"SELECT {COLUMNS} FROM tasks WHERE {VISIBLE}"
        if not include_done:
            sql += " AND done = 0"
        sql += f" ORDER BY {PRIORITY_ORDER}, due_date IS NULL, due_date, id"
        return [dict(row) for row in self.conn.execute(sql, {"me": self.me})]

    def get(self, task_id: int) -> dict | None:
        row = self.conn.execute(
            f"SELECT {COLUMNS} FROM tasks WHERE id = :id AND {VISIBLE}",
            {"id": task_id, "me": self.me},
        ).fetchone()
        return dict(row) if row else None

    def set_done(self, task_id: int, done: bool) -> bool:
        return self._update("done = :value", task_id, int(done))

    def set_priority(self, task_id: int, priority: str) -> bool:
        check_priority(priority)
        return self._update("priority = :value", task_id, priority)

    def delete(self, task_id: int) -> bool:
        with self.conn:
            cur = self.conn.execute(f"DELETE FROM tasks WHERE id = :id AND {VISIBLE}",
                                    {"id": task_id, "me": self.me})
        return cur.rowcount == 1

    def _update(self, assignment: str, task_id: int, value) -> bool:
        """True if a visible task was changed. `assignment` is never user input."""
        with self.conn:
            cur = self.conn.execute(
                f"UPDATE tasks SET {assignment} WHERE id = :id AND {VISIBLE}",
                {"value": value, "id": task_id, "me": self.me},
            )
        return cur.rowcount == 1
