"""Direct features of the web page: no model call, so 0 tokens and instant.

These routes call services/ directly. No ✅ / ❌ confirmation here: the
confirmations protect against the MODEL's decisions (it may have been
fooled by an email); a click in the page is already the user's decision.
Identity and CSRF checks still apply (web/server.py does them first).
"""

import threading
from contextlib import contextmanager

from ..services.household import user_data
from ..services.users import get_user


class BadRequest(ValueError):
    """Invalid input from the page (answered with HTTP 400)."""


class SharedDB:
    """The web server's one SQLite connection, used by several threads.

    A sqlite3 connection must not be used by two threads at once: every use
    goes through this one lock (all the web APIs share this object).
    """

    def __init__(self, conn):
        self.conn = conn
        self.lock = threading.Lock()

    def user(self, login: str):
        with self.lock:
            return get_user(self.conn, login)

    @contextmanager
    def data_for(self, user):
        """with db.data_for(user) as data: ... (holds the lock meanwhile)."""
        with self.lock:
            yield user_data(self.conn, user)


class TasksAPI:
    def __init__(self, db: SharedDB):
        self.db = db

    def get(self, user, path: str, query: dict) -> dict | None:
        """GET routes for this user. Returns None if the path is not ours."""
        if path == "/api/tasks":
            with self.db.data_for(user) as data:
                return {"tasks": data.tasks.list(include_done=query.get("all") == "1")}
        return None

    def post(self, user, path: str, data: dict) -> dict | None:
        """POST routes for this user. Returns None if the path is not ours.

        Here: only the SHAPE of the request (types). The rules (title length,
        valid date, priority...) are in services/tasks.py, for the agent too;
        their ValueError becomes HTTP 400 (web/server.py).
        """
        with self.db.data_for(user) as mine:
            tasks = mine.tasks
            if path == "/api/tasks/add":
                return tasks.add(field(data, "title", str),
                                 field(data, "due_date", str, optional=True) or None,
                                 field(data, "priority", str, optional=True) or "normal")

            if path == "/api/tasks/priority":
                return {"ok": tasks.set_priority(task_id_of(data), field(data, "priority", str))}

            if path == "/api/tasks/done":
                return {"ok": tasks.set_done(task_id_of(data), field(data, "done", bool))}

            if path == "/api/tasks/delete":
                return {"ok": tasks.delete(task_id_of(data))}
        return None


def field(data: dict, name: str, kind: type, optional: bool = False):
    """data[name], checked to be of this type (or missing/null if optional)."""
    value = data.get(name)
    if value is None and optional:
        return None
    if type(value) is not kind:  # not isinstance: True/False are ints in Python
        raise BadRequest(f"{name}: expected {kind.__name__}")
    return value


def task_id_of(data: dict) -> int:
    return field(data, "id", int)
