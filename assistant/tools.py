"""Tools the agent may call: JSON schemas for the model, Python functions for us.

Safety rules enforced here, in code (not in the prompt):
- ALLOWLIST: the model can only run tools listed in TOOLS. Any other name
  is refused.
- CONFIRMATION: tools in NEEDS_CONFIRMATION only run if the user says yes.
"""

import json
from typing import Callable

from .store import Store

# Tool definitions sent to the model. `strict: True` makes the API guarantee
# that the arguments match the schema (hence additionalProperties: false and
# every property listed in `required`; optional values are nullable).
TOOLS = [
    {
        "name": "add_task",
        "description": "Add a task to the to-do list.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short description of the task."},
                "due_date": {
                    "type": ["string", "null"],
                    "description": "Due date as YYYY-MM-DD, or null if none.",
                },
            },
            "required": ["title", "due_date"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_tasks",
        "description": "List tasks, sorted by due date. Returns id, title, due_date, done.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "include_done": {"type": "boolean", "description": "Also list finished tasks."},
            },
            "required": ["include_done"],
            "additionalProperties": False,
        },
    },
    {
        "name": "complete_task",
        "description": "Mark a task as done. Use list_tasks first to find its id.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "delete_task",
        "description": "Delete a task permanently. The user is asked to confirm.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "log_workout",
        "description": "Record a training session.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "day": {"type": "string", "description": "Date as YYYY-MM-DD."},
                "activity": {"type": "string", "description": "e.g. run, strength, swim, bike."},
                "duration_min": {"type": "integer", "description": "Duration in minutes."},
                "notes": {
                    "type": ["string", "null"],
                    "description": "Distance, feeling, exercises... or null.",
                },
            },
            "required": ["day", "activity", "duration_min", "notes"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_workouts",
        "description": "List training sessions from the last N days.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "description": "How many days back."}},
            "required": ["days"],
            "additionalProperties": False,
        },
    },
]

# Tools that change or destroy data the user cares about.
NEEDS_CONFIRMATION = {"delete_task"}

# A function that shows a question to the user and returns True for "yes".
ConfirmFn = Callable[[str], bool]


class ToolError(Exception):
    """An error the model should see (and can recover from)."""


class ToolBox:
    def __init__(self, store: Store, confirm: ConfirmFn):
        self.store = store
        self.confirm = confirm
        # name -> Python function. This dict IS the allowlist.
        self.functions = {
            "add_task": lambda a: store.add_task(a["title"], a["due_date"]),
            "list_tasks": lambda a: store.list_tasks(a["include_done"]),
            "complete_task": lambda a: self._check(store.complete_task(a["task_id"]), a),
            "delete_task": lambda a: self._check(store.delete_task(a["task_id"]), a),
            "log_workout": lambda a: store.log_workout(
                a["day"], a["activity"], a["duration_min"], a["notes"]
            ),
            "list_workouts": lambda a: store.list_workouts(a["days"]),
        }
        assert set(self.functions) == {t["name"] for t in TOOLS}

    @staticmethod
    def _check(found: bool, args: dict) -> dict:
        if not found:
            raise ToolError(f"No task with id {args['task_id']}.")
        return {"ok": True}

    def run(self, name: str, args: dict) -> str:
        """Run one tool and return its result as a JSON string.

        Raises ToolError for anything the model should be told about.
        """
        if name not in self.functions:
            raise ToolError(f"Unknown tool: {name}")

        if name in NEEDS_CONFIRMATION and not self.confirm(self._describe(name, args)):
            raise ToolError("The user declined this action. Do not retry it.")

        try:
            result = self.functions[name](args)
        except (ValueError, KeyError) as e:  # bad date, missing argument...
            raise ToolError(f"Invalid arguments: {e}") from e
        return json.dumps(result, ensure_ascii=False)

    def _describe(self, name: str, args: dict) -> str:
        if name == "delete_task":
            task = self.store.get_task(args["task_id"])
            label = task["title"] if task else f"#{args['task_id']} (not found)"
            return f"Delete task «{label}»?"
        return f"{name}({args})?"
