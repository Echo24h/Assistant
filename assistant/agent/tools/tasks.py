"""To-do list and training log tools (local SQLite, services/store.py).

Each tool module gives the ToolBox (tools/__init__.py) the same things:
DEFINITIONS (JSON schemas for the model), functions() (name -> Python
function), NEEDS_CONFIRMATION, NOT_LOGGED, check() and describe().
"""

# Tool definitions sent to the model. `strict: True` makes the API guarantee
# that the arguments match the schema (hence additionalProperties: false and
# every property listed in `required`; optional values are nullable).
DEFINITIONS = [
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

NEEDS_CONFIRMATION = {"delete_task"}
NOT_LOGGED = set()


def functions(store) -> dict:
    return {
        "add_task": lambda a: store.add_task(a["title"], a["due_date"]),
        "list_tasks": lambda a: store.list_tasks(a["include_done"]),
        "complete_task": lambda a: found(store.complete_task(a["task_id"]), a),
        "delete_task": lambda a: found(store.delete_task(a["task_id"]), a),
        "log_workout": lambda a: store.log_workout(
            a["day"], a["activity"], a["duration_min"], a["notes"]
        ),
        "list_workouts": lambda a: store.list_workouts(a["days"]),
    }


def found(ok: bool, args: dict) -> dict:
    if not ok:
        raise ValueError(f"No task with id {args['task_id']}.")
    return {"ok": True}


def check(store, name: str, args: dict) -> None:
    """Nothing to check before confirmation for tasks."""


def describe(store, name: str, args: dict) -> str:
    """The question shown to the user before a sensitive action."""
    task = store.get_task(args["task_id"])
    label = task["title"] if task else f"#{args['task_id']} (not found)"
    return f"Delete task «{label}»?"
