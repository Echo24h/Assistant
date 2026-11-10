"""Local SQLite storage for the to-do list and the training log."""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    due_date   TEXT,               -- ISO date (YYYY-MM-DD) or NULL
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS workouts (
    id           INTEGER PRIMARY KEY,
    day          TEXT NOT NULL,    -- ISO date
    activity     TEXT NOT NULL,    -- e.g. "run", "strength", "swim"
    duration_min INTEGER NOT NULL,
    notes        TEXT
);
"""


class Store:
    def __init__(self, db_path: Path | str):
        # check_same_thread=False: the web interface runs each conversation in
        # its own thread; one conversation never runs two turns at once.
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # rows behave like dicts
        self.conn.executescript(SCHEMA)

    # --- tasks ---

    def add_task(self, title: str, due_date: str | None) -> dict:
        if due_date:
            date.fromisoformat(due_date)  # raises ValueError on a bad date
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", (title, due_date)
        )
        self.conn.commit()
        return {"id": cur.lastrowid, "title": title, "due_date": due_date}

    def list_tasks(self, include_done: bool) -> list[dict]:
        sql = "SELECT id, title, due_date, done FROM tasks"
        if not include_done:
            sql += " WHERE done = 0"
        sql += " ORDER BY due_date IS NULL, due_date, id"
        return [dict(row) for row in self.conn.execute(sql)]

    def get_task(self, task_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT id, title, due_date, done FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    def complete_task(self, task_id: int) -> bool:
        cur = self.conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        self.conn.commit()
        return cur.rowcount == 1

    def reopen_task(self, task_id: int) -> bool:
        cur = self.conn.execute("UPDATE tasks SET done = 0 WHERE id = ?", (task_id,))
        self.conn.commit()
        return cur.rowcount == 1

    def delete_task(self, task_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()
        return cur.rowcount == 1

    # --- workouts ---

    def log_workout(self, day: str, activity: str, duration_min: int, notes: str | None) -> dict:
        date.fromisoformat(day)
        if duration_min <= 0:
            raise ValueError("duration_min must be positive")
        cur = self.conn.execute(
            "INSERT INTO workouts (day, activity, duration_min, notes) VALUES (?, ?, ?, ?)",
            (day, activity, duration_min, notes),
        )
        self.conn.commit()
        return {"id": cur.lastrowid, "day": day, "activity": activity, "duration_min": duration_min}

    def list_workouts(self, days: int, today: date | None = None) -> list[dict]:
        since = (today or date.today()) - timedelta(days=days)
        rows = self.conn.execute(
            "SELECT id, day, activity, duration_min, notes FROM workouts "
            "WHERE day >= ? ORDER BY day",
            (since.isoformat(),),
        )
        return [dict(row) for row in rows]
