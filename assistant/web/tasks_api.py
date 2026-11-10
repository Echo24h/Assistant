"""Tasks tab: the to-do list, read and changed directly (services/tasks.py)."""

from .api import SharedDB, field, id_of


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
                return {"ok": tasks.set_priority(id_of(data), field(data, "priority", str))}

            if path == "/api/tasks/done":
                return {"ok": tasks.set_done(id_of(data), field(data, "done", bool))}

            if path == "/api/tasks/delete":
                return {"ok": tasks.delete(id_of(data))}
        return None
