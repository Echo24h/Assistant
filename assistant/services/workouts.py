"""The training log: always personal."""

import sqlite3
from datetime import date, timedelta

from .users import User


def give_old_workouts_to(conn: sqlite3.Connection, owner: User) -> None:
    """Workouts logged before users existed (user_id NULL) belong to the owner."""
    with conn:
        conn.execute("UPDATE workouts SET user_id = ? WHERE user_id IS NULL", (owner.id,))


class Workouts:
    def __init__(self, conn: sqlite3.Connection, user: User):
        self.conn = conn
        self.me = user.id

    def log(self, day: str, activity: str, duration_min: int, notes: str | None) -> dict:
        date.fromisoformat(day)
        if duration_min <= 0:
            raise ValueError("duration_min must be positive")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO workouts (user_id, day, activity, duration_min, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                (self.me, day, activity, duration_min, notes),
            )
        return {"id": cur.lastrowid, "day": day, "activity": activity,
                "duration_min": duration_min}

    def list(self, days: int, today: date | None = None) -> list[dict]:
        since = (today or date.today()) - timedelta(days=days)
        rows = self.conn.execute(
            "SELECT id, day, activity, duration_min, notes FROM workouts "
            "WHERE user_id = ? AND day >= ? ORDER BY day",
            (self.me, since.isoformat()),
        )
        return [dict(row) for row in rows]
