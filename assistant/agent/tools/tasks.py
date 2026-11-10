"""To-do list and training log tools (services/tasks.py, services/workouts.py).

Each tool module gives the ToolBox (tools/__init__.py) the same things:
DEFINITIONS (JSON schemas for the model), functions() (name -> Python
function), NEEDS_CONFIRMATION, NOT_LOGGED, check() and describe().
"""

PRIORITY = {
    "type": "string",
    "enum": ["high", "normal", "low"],
    "description": "normal unless the user says it is urgent/important (high) "
                   "or can wait (low).",
}

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
                "priority": PRIORITY,
            },
            "required": ["title", "due_date", "priority"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_tasks",
        "description": "List tasks, most important first, then by due date. "
                       "Returns id, title, due_date, priority, done.",
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
        "name": "set_task_priority",
        "description": "Change the priority of a task. Use list_tasks first to find its id.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}, "priority": PRIORITY},
            "required": ["task_id", "priority"],
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


def functions(data) -> dict:
    """data: services.data.UserData (tasks and workouts of this person)."""
    return {
        "add_task": lambda a: data.tasks.add(a["title"], a["due_date"], a["priority"]),
        "list_tasks": lambda a: data.tasks.list(a["include_done"]),
        "complete_task": lambda a: found(data.tasks.set_done(a["task_id"], True), a),
        "set_task_priority": lambda a: found(
            data.tasks.set_priority(a["task_id"], a["priority"]), a),
        "delete_task": lambda a: found(data.tasks.delete(a["task_id"]), a),
        "log_workout": lambda a: data.workouts.log(
            a["day"], a["activity"], a["duration_min"], a["notes"]
        ),
        "list_workouts": lambda a: data.workouts.list(a["days"]),
    }


def found(ok: bool, args: dict) -> dict:
    if not ok:
        raise ValueError(f"No task with id {args['task_id']}.")
    return {"ok": True}


def check(data, name: str, args: dict) -> None:
    """Nothing to check before confirmation for tasks."""


def describe(data, name: str, args: dict) -> str:
    """The question shown to the user before a sensitive action."""
    task = data.tasks.get(args["task_id"])
    label = task["title"] if task else f"#{args['task_id']} (not found)"
    return f"Delete task «{label}»?"
