"""A fresh in-memory database with a household, for tests."""

from assistant.services.data import UserData, user_data
from assistant.services.db import connect
from assistant.services.users import get_user, sync_users

PEOPLE = {"me@x.com": "Grégory", "her@x.com": "Anna"}


def household():
    """(conn, me, her) on a new in-memory database."""
    conn = connect(":memory:")
    sync_users(conn, PEOPLE)
    return conn, get_user(conn, "me@x.com"), get_user(conn, "her@x.com")


def memory_data() -> UserData:
    conn, me, _ = household()
    return user_data(conn, me)
