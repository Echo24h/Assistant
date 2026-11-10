"""Database layer: migrations, users, tasks shared or private."""

import json
import sqlite3

import pytest

from assistant.agent.tools import ToolBox, ToolError
from assistant.services.data import open_household, user_data
from assistant.services.db import connect, migrations
from helpers import household


@pytest.fixture
def data():
    conn, me, _ = household()
    return user_data(conn, me)


def test_tasks_lifecycle(data):
    a = data.tasks.add("Pay rent", "2026-12-01")
    data.tasks.add("Call mum", None)
    assert [t["title"] for t in data.tasks.list(False)] == ["Pay rent", "Call mum"]
    assert data.tasks.set_done(a["id"], True)
    assert [t["title"] for t in data.tasks.list(False)] == ["Call mum"]
    assert len(data.tasks.list(True)) == 2
    assert data.tasks.set_done(a["id"], False)  # reopen
    assert len(data.tasks.list(False)) == 2


def test_priority_sorts_first_then_due_date(data):
    data.tasks.add("Later", "2026-11-11", "low")
    data.tasks.add("Soon", "2026-11-12")
    urgent = data.tasks.add("Urgent", None, "high")
    assert [t["title"] for t in data.tasks.list(False)] == ["Urgent", "Soon", "Later"]

    assert data.tasks.set_priority(urgent["id"], "low")
    assert data.tasks.list(False)[-1]["title"] == "Urgent"
    with pytest.raises(ValueError):
        data.tasks.set_priority(urgent["id"], "very high")


def test_shared_tasks_and_private_tasks():
    conn, me, her = household()
    mine, hers = user_data(conn, me).tasks, user_data(conn, her).tasks

    shared = mine.add("Buy a sofa", None)
    secret = mine.add("Birthday present for Anna", None, private=True)
    assert [t["title"] for t in hers.list(False)] == ["Buy a sofa"]  # shared by default
    assert len(mine.list(False)) == 2

    # Knowing the id is not enough: the private task is untouchable for her.
    assert hers.get(secret["id"]) is None
    assert not hers.set_done(secret["id"], True)
    assert not hers.set_priority(secret["id"], "low")
    assert not hers.delete(secret["id"])
    assert mine.get(secret["id"])["done"] == 0

    assert hers.set_done(shared["id"], True)  # a shared task: she can
    assert mine.get(shared["id"])["done"] == 1


def test_rules_apply_to_the_agent_too(data):
    box = ToolBox(data, confirm=lambda q: True)
    with pytest.raises(ToolError):
        box.run("add_task", {"title": "x", "due_date": "next week", "priority": "normal"})
    with pytest.raises(ToolError, match="title"):
        box.run("add_task", {"title": "  ", "due_date": None, "priority": "normal"})
    with pytest.raises(ToolError, match="title"):
        box.run("add_task", {"title": "x" * 201, "due_date": None, "priority": "normal"})


def test_unknown_tool_is_refused(data):
    box = ToolBox(data, confirm=lambda q: True)
    with pytest.raises(ToolError, match="Unknown tool"):
        box.run("send_email", {"to": "attacker@example.com"})


def test_delete_needs_confirmation(data):
    task = data.tasks.add("Keep me", None)
    box = ToolBox(data, confirm=lambda q: False)  # user says no
    with pytest.raises(ToolError, match="declined"):
        box.run("delete_task", {"task_id": task["id"]})
    assert data.tasks.get(task["id"]) is not None  # still there

    box = ToolBox(data, confirm=lambda q: True)  # user says yes
    assert json.loads(box.run("delete_task", {"task_id": task["id"]})) == {"ok": True}
    assert data.tasks.get(task["id"]) is None


def test_database_constraints_catch_bugs(data):
    with pytest.raises(sqlite3.IntegrityError):  # CHECK constraint
        data.tasks.conn.execute("INSERT INTO tasks (title, priority) VALUES ('x', 'urgent')")
    with pytest.raises(sqlite3.IntegrityError):  # foreign key: no user 999
        data.tasks.conn.execute("INSERT INTO tasks (title, owner_id) VALUES ('x', 999)")


def test_migrations_are_numbered_without_gaps():
    numbers = [number for number, _ in migrations()]
    assert numbers == list(range(1, len(numbers) + 1))


def test_database_from_before_migrations_keeps_its_data(tmp_path):
    """The real database of version 0: tasks with priority, workouts, no users.
    Tasks are kept; the workouts table is dropped by 003."""
    db = tmp_path / "old.db"
    old = sqlite3.connect(db)
    old.executescript("""
        CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, due_date TEXT,
            done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            priority TEXT NOT NULL DEFAULT 'normal');
        CREATE TABLE workouts (id INTEGER PRIMARY KEY, day TEXT NOT NULL,
            activity TEXT NOT NULL, duration_min INTEGER NOT NULL, notes TEXT);
        INSERT INTO tasks (title, priority) VALUES ('Old task', 'high');
        INSERT INTO workouts (day, activity, duration_min) VALUES ('2026-11-09', 'run', 30);
    """)
    old.close()

    conn, owner = open_household(db, {"me@x.com": "Grégory"})
    data = user_data(conn, owner)
    task = data.tasks.list(False)[0]
    assert (task["title"], task["priority"], task["private"]) == ("Old task", "high", 0)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    assert "workouts" not in tables
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(migrations())

    connect(db)  # opening again changes nothing
