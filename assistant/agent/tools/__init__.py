"""The ToolBox: which tools the model may call, and the safety rules.

Safety rules enforced here, in code (not in the prompt):
- ALLOWLIST: the model can only run tools of the domains given to the
  ToolBox. Any other name is refused.
- CONFIRMATION: tools listed in a domain's NEEDS_CONFIRMATION only run if
  the user says yes. Obvious mistakes are caught before asking (check).

- STRICT: the API guarantees that the arguments match the schema. Set
  here, for the tools that need confirmation only: the question shown to
  the user must describe exactly what will run. (The API limits strict
  tools: at most 20, and a limited total grammar size.) The other tools'
  arguments are checked by our code: a missing one is a ToolError.

Each domain (tasks.py, recipes.py, shopping.py, products.py, finances.py, bugs.py, calendar.py, gmail.py) brings its own tools; later,
the domains given to the ToolBox can depend on who is talking.
"""

import json
from typing import Callable

from . import bugs as bug_tools
from . import calendar as calendar_tools
from . import finances as finance_tools
from . import gmail as gmail_tools
from . import products as product_tools
from . import recipes as recipe_tools
from . import shopping as shopping_tools
from . import tasks as task_tools

# A function that shows a question to the user and returns True for "yes".
ConfirmFn = Callable[[str], bool]


class ToolError(Exception):
    """An error the model should see (and can recover from)."""


class ToolBox:
    def __init__(self, data, confirm: ConfirmFn, calendar=None, gmail=None):
        """data: services.household.UserData, what this person can see and change."""
        self.data = data
        self.confirm = confirm
        self.definitions = []  # what the model is told it can call
        self.functions = {}  # name -> Python function. This dict IS the allowlist.
        self.needs_confirmation = set()
        self.not_logged = set()  # tool outputs never written to the log
        self.owner = {}  # name -> (domain module, service), for check/describe

        self._add(task_tools, data)
        self._add(recipe_tools, data)
        self._add(shopping_tools, data)
        self._add(product_tools, data)
        self._add(finance_tools, data)
        self._add(bug_tools, data)
        if calendar is not None:
            self._add(calendar_tools, calendar)
        if gmail is not None:
            self._add(gmail_tools, gmail)

        assert set(self.functions) == {t["name"] for t in self.definitions}

    def close(self) -> None:
        self.data.close()

    def _add(self, domain, service) -> None:
        functions = domain.functions(service)
        self.functions |= functions
        self.definitions += [{**tool, "strict": tool["name"] in domain.NEEDS_CONFIRMATION}
                             for tool in domain.DEFINITIONS]
        self.needs_confirmation |= domain.NEEDS_CONFIRMATION
        self.not_logged |= domain.NOT_LOGGED
        for name in functions:
            self.owner[name] = (domain, service)

    def run(self, name: str, args: dict) -> str:
        """Run one tool and return its result as a JSON string.

        Raises ToolError for anything the model should be told about.
        """
        if name not in self.functions:
            raise ToolError(f"Unknown tool: {name}")

        domain, service = self.owner[name]
        try:
            domain.check(service, name, args)
            if name in self.needs_confirmation and not self.confirm(
                    domain.describe(service, name, args)):
                raise ToolError("The user declined this action. Do not retry it.")
            result = self.functions[name](args)
        except KeyError as e:  # a non-strict tool called without an argument
            raise ToolError(f"Missing argument: {e}") from e
        except ValueError as e:  # bad date, unknown id, Google error...
            raise ToolError(str(e)) from e
        return json.dumps(result, ensure_ascii=False)
