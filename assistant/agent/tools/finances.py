"""Shared expense tools (services/finances.py). Shared by the household.

Amounts go to the model as text ("45.50 CHF"), never as raw cents.
"""

from ...services.finances import CATEGORIES, SPLITS, money, to_cents

DEFINITIONS = [
    {
        "name": "add_expense",
        "description": "Record a household expense. The user is asked to confirm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "e.g. 45.5"},
                "description": {"type": "string", "description": "What, e.g. 'Courses Migros'."},
                "category": {"type": "string", "enum": list(CATEGORIES)},
                "day": {"type": ["string", "null"], "description": "YYYY-MM-DD, null = today."},
                "paid_by": {"type": ["string", "null"],
                            "description": "Name of the person who paid, null = the user."},
                "split": {"type": "string", "enum": list(SPLITS),
                          "description": "equal = shared equally (default). for_others = "
                                         "paid entirely for the other person, or a "
                                         "repayment (category remboursement)."},
            },
            "required": ["amount", "description", "category", "day", "paid_by", "split"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_expenses",
        "description": "Expenses of a month, with totals per category.",
        "input_schema": {
            "type": "object",
            "properties": {"month": {"type": ["string", "null"],
                                     "description": "YYYY-MM, null = this month."}},
            "required": ["month"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_balance",
        "description": "Who owes whom in the household, and how much.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "delete_expense",
        "description": "Delete an expense. Use list_expenses first to find its id. "
                       "The user is asked to confirm.",
        "input_schema": {
            "type": "object",
            "properties": {"expense_id": {"type": "integer"}},
            "required": ["expense_id"],
            "additionalProperties": False,
        },
    },
]

NEEDS_CONFIRMATION = {"add_expense", "delete_expense"}
NOT_LOGGED = set()


def functions(data) -> dict:
    """data: services.household.UserData."""
    finances = data.finances
    return {
        "add_expense": lambda a: readable(finances, finances.add(
            a["amount"], a["description"], a["category"], a["day"],
            payer_id(finances, a["paid_by"]), a["split"])),
        "list_expenses": lambda a: {
            "expenses": [readable(finances, e) for e in finances.list(a.get("month"))],
            "by_category": {c: money(cents, finances.currency)
                            for c, cents in finances.by_category(a.get("month")).items()},
        },
        "get_balance": lambda a: balance(finances),
        "delete_expense": lambda a: delete_expense(finances, a["expense_id"]),
    }


def payer_id(finances, name: str | None) -> int | None:
    """"Anna" -> her user id; None -> None (the user). Unknown name: an error."""
    if name is None:
        return None
    for person in finances.people():
        if person.name.casefold() == name.strip().casefold():
            return person.id
    names = ", ".join(p.name for p in finances.people())
    raise ValueError(f"Unknown person: {name}. The household: {names}.")


def readable(finances, expense: dict) -> dict:
    """The expense with "45.50 CHF" instead of amount_cents."""
    result = {k: v for k, v in expense.items() if k != "amount_cents"}
    result["amount"] = money(expense["amount_cents"], finances.currency)
    return result


def balance(finances) -> dict:
    payments = finances.settle_up()
    return {"to_settle": [f"{p['from']} owes {p['to']} "
                          f"{money(p['amount_cents'], finances.currency)}" for p in payments]
            or ["Nothing to settle: everyone is even."]}


def delete_expense(finances, expense_id: int) -> dict:
    if not finances.delete(expense_id):
        raise ValueError(f"No expense with id {expense_id}.")
    return {"ok": True}


def check(data, name: str, args: dict) -> None:
    """Catch mistakes before asking: unknown payer, bad amount or category."""
    if name == "add_expense":
        to_cents(args["amount"])
        payer_id(data.finances, args["paid_by"])


def describe(data, name: str, args: dict) -> str:
    finances = data.finances
    if name == "add_expense":
        payer = args["paid_by"] or data.user.name
        how = "shared equally" if args["split"] == "equal" else "entirely for the other(s)"
        amount = money(to_cents(args["amount"]), finances.currency)
        return (f"Add «{args['description']}» ({args['category']}), {amount} "
                f"paid by {payer}, {how}?")
    expense = finances.get(args["expense_id"])
    label = (f"«{expense['description']}» {money(expense['amount_cents'], finances.currency)} "
             f"({expense['day']})") if expense else f"#{args['expense_id']} (not found)"
    return f"Delete the expense {label}?"
