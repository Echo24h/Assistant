"""The people of the household.

The list comes from the config (ASSISTANT_WEB_USERS): the database follows
it at start. The first person is the owner: their Google accounts are
connected, and the terminal acts in their name.
"""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    login: str
    name: str


def sync_users(conn: sqlite3.Connection, people: dict[str, str]) -> User:
    """Add or rename the people of the config; return the owner (the first).

    Nobody is ever deleted: tasks and expenses refer to them.
    """
    if not people:
        raise ValueError("At least one user is needed.")
    with conn:  # one transaction, committed at the end
        for login, name in people.items():
            conn.execute(
                "INSERT INTO users (login, name) VALUES (?, ?) "
                "ON CONFLICT (login) DO UPDATE SET name = excluded.name",
                (login, name),
            )
        owner = get_user(conn, next(iter(people)))
        # Workouts logged before users existed belong to the owner.
        conn.execute("UPDATE workouts SET user_id = ? WHERE user_id IS NULL", (owner.id,))
    return owner


def get_user(conn: sqlite3.Connection, login: str) -> User | None:
    row = conn.execute("SELECT id, login, name FROM users WHERE login = ?", (login,)).fetchone()
    return User(**row) if row else None


def list_users(conn: sqlite3.Connection) -> list[User]:
    return [User(**row) for row in conn.execute("SELECT id, login, name FROM users ORDER BY id")]
