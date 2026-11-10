"""Bug reports, written by the household, read and closed by the owner.

Stored locally only. Creating a GitHub issue automatically would give the
app (and the agent) a way to send data to the internet: not done.
"""

import sqlite3

from .users import User

MAX_DESCRIPTION = 2000
MAX_DETAILS = 8000
MAX_IMAGE = 2_000_000  # bytes
# An image is recognized by its first bytes, not by what the sender claims.
IMAGE_TYPES = {b"\xff\xd8\xff": "jpg", b"\x89PNG\r\n\x1a\n": "png"}


def image_type(image: bytes) -> str:
    """"jpg" or "png"; ValueError for anything else."""
    for start, extension in IMAGE_TYPES.items():
        if image.startswith(start):
            return extension
    raise ValueError("image: JPEG or PNG only")


class Bugs:
    def __init__(self, conn: sqlite3.Connection, user: User):
        self.conn = conn
        self.me = user.id

    def report(self, description: str, place: str, details: str | None = None,
               version: str | None = None, image: bytes | None = None) -> dict:
        description = description.strip()
        if not 0 < len(description) <= MAX_DESCRIPTION:
            raise ValueError(f"description: 1 to {MAX_DESCRIPTION} characters")
        place = place.strip()[:30] or "unknown"
        details = (details or "")[:MAX_DETAILS] or None  # cut, never refused
        if image is not None:
            if len(image) > MAX_IMAGE:
                raise ValueError("image: 2 MB at most")
            image_type(image)
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO bug_reports (description, place, details, version, image, "
                "reported_by) VALUES (?, ?, ?, ?, ?, ?)",
                (description, place, details, version, image, self.me),
            )
        return {"id": cur.lastrowid, "status": "open"}

    def list(self, status: str = "open") -> list[dict]:
        rows = self.conn.execute(
            # Stored in UTC by SQLite (datetime('now')); shown in local time.
            "SELECT b.id, datetime(b.created_at, 'localtime') AS created_at, u.name AS reported_by, b.place, b.description, "
            "b.details, b.version, b.status, b.image IS NOT NULL AS has_image "
            "FROM bug_reports b LEFT JOIN users u ON u.id = b.reported_by "
            "WHERE b.status = ? ORDER BY b.id",
            (status,),
        )
        return [dict(row) for row in rows]

    def image(self, bug_id: int) -> bytes | None:
        row = self.conn.execute("SELECT image FROM bug_reports WHERE id = ?", (bug_id,)).fetchone()
        return row["image"] if row else None

    def set_status(self, bug_id: int, status: str) -> bool:
        if status not in ("open", "fixed"):
            raise ValueError("status: open or fixed")
        with self.conn:
            cur = self.conn.execute("UPDATE bug_reports SET status = ? WHERE id = ?",
                                    (status, bug_id))
        return cur.rowcount == 1
