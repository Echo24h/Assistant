"""Direct features of the web page: no model call, so 0 tokens and instant.

These routes call services/ directly. No ✅ / ❌ confirmation here: the
confirmations protect against the MODEL's decisions (it may have been
fooled by an email); a click in the page is already the user's decision.
Identity and CSRF checks still apply (web/server.py does them first).

This file: what all the domain APIs share. One file per domain next to it
(tasks_api.py, recipes_api.py, shopping_api.py), like services/.
Each API has get(user, path, query) and post(user, path, data), which
return None when the path is not theirs.
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


def field(data: dict, name: str, kind: type, optional: bool = False):
    """data[name], checked to be of this type (or missing/null if optional)."""
    value = data.get(name)
    if value is None and optional:
        return None
    if type(value) is not kind:  # not isinstance: True/False are ints in Python
        raise BadRequest(f"{name}: expected {kind.__name__}")
    return value


def id_of(data: dict) -> int:
    return field(data, "id", int)


def query_id(query: dict) -> int:
    """?id=12 in a GET request."""
    try:
        return int(query.get("id", ""))
    except ValueError:
        raise BadRequest("id: an integer") from None
