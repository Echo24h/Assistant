"""Everything one person can read and change, in one object.

Built once per conversation (agent) or per request (web page). Each domain
filters by this user, so the code above never has to think about it.
Later: finances.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .db import connect
from .recipes import Recipes
from .shopping import Shopping
from .tasks import Tasks
from .users import User, sync_users


def open_household(path: Path | str, people: dict[str, str]):
    """Open and upgrade the database, sync the people; return (conn, owner)."""
    conn = connect(path)
    owner = sync_users(conn, people)
    return conn, owner


@dataclass(frozen=True)
class UserData:
    conn: sqlite3.Connection
    user: User
    tasks: Tasks
    recipes: Recipes
    shopping: Shopping

    def close(self) -> None:
        """Close the connection, when this data has its own (app.build_agent)."""
        self.conn.close()


def user_data(conn: sqlite3.Connection, user: User) -> UserData:
    recipes = Recipes(conn, user)
    return UserData(conn=conn, user=user, tasks=Tasks(conn, user), recipes=recipes,
                    shopping=Shopping(conn, user, recipes))
