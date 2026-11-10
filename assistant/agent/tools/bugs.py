"""Bug report tool (services/bugs.py): stored locally, read by the owner."""

from ...version import code_version

DEFINITIONS = [
    {
        "name": "report_bug",
        "description": "Record a bug of this assistant when the user reports one "
                       "(or asks you to). Describe what the user did, what happened "
                       "and what was expected, with any error message.",
        "input_schema": {
            "type": "object",
            "properties": {"description": {"type": "string"}},
            "required": ["description"],
            "additionalProperties": False,
        },
    },
]

NEEDS_CONFIRMATION = set()  # harmless: a local note for the owner
NOT_LOGGED = set()


def functions(data) -> dict:
    """data: services.household.UserData."""
    return {
        "report_bug": lambda a: data.bugs.report(a["description"], "agent",
                                                 version=code_version()),
    }


def check(data, name: str, args: dict) -> None:
    """Nothing to check."""


def describe(data, name: str, args: dict) -> str:
    raise AssertionError("report_bug needs no confirmation")
