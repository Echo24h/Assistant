"""Direct features of the web page: no model call, so 0 tokens and instant.

These routes call services/ directly. No ✅ / ❌ confirmation here: the
confirmations protect against the MODEL's decisions (it may have been
fooled by an email); a click in the page is already the user's decision.
Identity and CSRF checks still apply (web/server.py does them first).
"""

import threading
from datetime import date

from ..services.data import user_data
from ..services.tasks import PRIORITIES


class BadRequest(ValueError):
    """Invalid input from the page (answered with HTTP 400)."""


class TasksAPI:
    def __init__(self, conn):
        self.conn = conn
        self.lock = threading.Lock()  # one SQLite connection, several web threads

    def get(self, user, path: str, query: dict) -> dict | None:
        """GET routes for this user. Returns None if the path is not ours."""
        if path == "/api/tasks":
            with self.lock:
                tasks = user_data(self.conn, user).tasks
                return {"tasks": tasks.list(include_done=query.get("all") == "1")}
        return None

    def post(self, user, path: str, data: dict) -> dict | None:
        """POST routes for this user. Returns None if the path is not ours."""
        with self.lock:
            tasks = user_data(self.conn, user).tasks
            if path == "/api/tasks/add":
                title = data.get("title")
                if not isinstance(title, str) or not 0 < len(title.strip()) <= 200:
                    raise BadRequest("title: 1 to 200 characters")
                due = data.get("due_date") or None
                if due is not None:
                    check_date(due)
                return tasks.add(title.strip(), due, priority_of(data, default="normal"))

            if path == "/api/tasks/priority":
                return {"ok": tasks.set_priority(task_id_of(data), priority_of(data))}

            if path == "/api/tasks/done":
                task_id, done = task_id_of(data), data.get("done")
                if not isinstance(done, bool):
                    raise BadRequest("done: true or false")
                return {"ok": tasks.set_done(task_id, done)}

            if path == "/api/tasks/delete":
                return {"ok": tasks.delete(task_id_of(data))}
        return None


def task_id_of(data: dict) -> int:
    task_id = data.get("id")
    if type(task_id) is not int:  # not isinstance: True/False are ints in Python
        raise BadRequest("id: an integer")
    return task_id


def priority_of(data: dict, default: str | None = None) -> str:
    priority = data.get("priority", default)
    if priority not in PRIORITIES:
        raise BadRequest(f"priority: one of {', '.join(PRIORITIES)}")
    return priority


def check_date(value) -> None:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        raise BadRequest("due_date: YYYY-MM-DD or null") from None
