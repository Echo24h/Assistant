"""Direct features of the web page: no model call, so 0 tokens and instant.

These routes call services/ directly. No ✅ / ❌ confirmation here: the
confirmations protect against the MODEL's decisions (it may have been
fooled by an email); a click in the page is already the user's decision.
Identity and CSRF checks still apply (web/server.py does them first).
"""

import threading
from datetime import date


class BadRequest(ValueError):
    """Invalid input from the page (answered with HTTP 400)."""


class TasksAPI:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()  # one SQLite connection, several web threads

    def get(self, path: str, query: dict) -> dict | None:
        """GET routes. Returns None if the path is not ours."""
        if path == "/api/tasks":
            with self.lock:
                return {"tasks": self.store.list_tasks(include_done=query.get("all") == "1")}
        return None

    def post(self, path: str, data: dict) -> dict | None:
        """POST routes. Returns None if the path is not ours."""
        with self.lock:
            if path == "/api/tasks/add":
                title = data.get("title")
                if not isinstance(title, str) or not 0 < len(title.strip()) <= 200:
                    raise BadRequest("title: 1 to 200 characters")
                due = data.get("due_date") or None
                if due is not None:
                    check_date(due)
                return self.store.add_task(title.strip(), due)

            if path == "/api/tasks/done":
                task_id, done = task_id_of(data), data.get("done")
                if not isinstance(done, bool):
                    raise BadRequest("done: true or false")
                ok = self.store.complete_task(task_id) if done else self.store.reopen_task(task_id)
                return {"ok": ok}

            if path == "/api/tasks/delete":
                return {"ok": self.store.delete_task(task_id_of(data))}
        return None


def task_id_of(data: dict) -> int:
    task_id = data.get("id")
    if type(task_id) is not int:  # not isinstance: True/False are ints in Python
        raise BadRequest("id: an integer")
    return task_id


def check_date(value) -> None:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        raise BadRequest("due_date: YYYY-MM-DD or null") from None
