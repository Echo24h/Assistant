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
        box.run("add_task", {"title": "x", "due_date": "next week"})


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
