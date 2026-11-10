import json
from datetime import date

import pytest

from assistant.services.store import Store
from assistant.agent.tools import ToolBox, ToolError


@pytest.fixture
def store():
    return Store(":memory:")


def test_tasks_lifecycle(store):
    a = store.add_task("Pay rent", "2026-12-01")
    store.add_task("Call mum", None)
    assert [t["title"] for t in store.list_tasks(False)] == ["Pay rent", "Call mum"]
    assert store.complete_task(a["id"])
    assert [t["title"] for t in store.list_tasks(False)] == ["Call mum"]
    assert len(store.list_tasks(True)) == 2


def test_bad_date_is_a_tool_error(store):
    box = ToolBox(store, confirm=lambda q: True)
    with pytest.raises(ToolError):
        box.run("add_task", {"title": "x", "due_date": "next week", "priority": "normal"})


def test_unknown_tool_is_refused(store):
    box = ToolBox(store, confirm=lambda q: True)
    with pytest.raises(ToolError, match="Unknown tool"):
        box.run("send_email", {"to": "attacker@example.com"})


def test_delete_needs_confirmation(store):
    task = store.add_task("Keep me", None)
    box = ToolBox(store, confirm=lambda q: False)  # user says no
    with pytest.raises(ToolError, match="declined"):
        box.run("delete_task", {"task_id": task["id"]})
    assert store.get_task(task["id"]) is not None  # still there

    box = ToolBox(store, confirm=lambda q: True)  # user says yes
    assert json.loads(box.run("delete_task", {"task_id": task["id"]})) == {"ok": True}
    assert store.get_task(task["id"]) is None


def test_workouts_window(store):
    store.log_workout("2026-11-01", "run", 40, "8 km")
    store.log_workout("2026-11-09", "strength", 30, None)
    recent = store.list_workouts(7, today=date(2026, 11, 10))
    assert [w["activity"] for w in recent] == ["strength"]


def test_priority_sorts_first_then_due_date(store):
    store.add_task("Later", "2026-11-11", "low")
    store.add_task("Soon", "2026-11-12")
    urgent = store.add_task("Urgent", None, "high")
    assert [t["title"] for t in store.list_tasks(False)] == ["Urgent", "Soon", "Later"]

    assert store.set_priority(urgent["id"], "low")
    assert store.list_tasks(False)[-1]["title"] == "Urgent"
    with pytest.raises(ValueError):
        store.set_priority(urgent["id"], "very high")


def test_old_database_gets_priority_without_losing_tasks(tmp_path):
    import sqlite3
    db = tmp_path / "old.db"
    old = sqlite3.connect(db)  # the table as it was before priorities
    old.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, "
                "due_date TEXT, done INTEGER NOT NULL DEFAULT 0, "
                "created_at TEXT NOT NULL DEFAULT (datetime('now')))")
    old.execute("INSERT INTO tasks (title) VALUES ('Old task')")
    old.commit()
    old.close()

    tasks = Store(db).list_tasks(False)
    assert tasks[0]["title"] == "Old task" and tasks[0]["priority"] == "normal"
