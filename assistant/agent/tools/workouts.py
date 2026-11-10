"""Training log tools (services/workouts.py). Same shape as tasks.py."""

DEFINITIONS = [
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

NEEDS_CONFIRMATION = set()
NOT_LOGGED = set()


def functions(data) -> dict:
    """data: services.data.UserData (what this person can see)."""
    return {
        "log_workout": lambda a: data.workouts.log(
            a["day"], a["activity"], a["duration_min"], a["notes"]
        ),
        "list_workouts": lambda a: data.workouts.list(a["days"]),
    }


def check(data, name: str, args: dict) -> None:
    """Nothing to check before running."""


def describe(data, name: str, args: dict) -> str:
    raise AssertionError("no workout tool needs confirmation")
