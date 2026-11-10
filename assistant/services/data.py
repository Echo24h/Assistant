"""Everything one person can read and change, in one object.

Built once per conversation (agent) or per request (web page). Each domain
filters by this user, so the code above never has to think about it.
Later: recipes, shopping, finances.
"""

import sqlite3
from dataclasses import dataclass

from .tasks import Tasks
from .users import User
from .workouts import Workouts


@dataclass(frozen=True)
class UserData:
    user: User
    tasks: Tasks
    workouts: Workouts


def user_data(conn: sqlite3.Connection, user: User) -> UserData:
    return UserData(user=user, tasks=Tasks(conn, user), workouts=Workouts(conn, user))
