"""Shopping list tools (services/shopping.py). The list is shared by the household.

No confirmation: adding to or removing from a list is harmless and easy
to undo in the Shopping tab.
"""

from .recipes import INGREDIENTS

DEFINITIONS = [
    {
        "name": "add_to_shopping_list",
        "description": "Add items to the shopping list (same items are added up).",
        "input_schema": {
            "type": "object",
            "properties": {"items": INGREDIENTS},
            "required": ["items"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_recipe_to_shopping_list",
        "description": "Add a saved recipe's ingredients to the shopping list, scaled "
                       "to a number of people.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe_id": {"type": "integer"},
                "servings": {"type": ["integer", "null"],
                             "description": "Number of people, or null for the recipe's."},
            },
            "required": ["recipe_id", "servings"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_shopping_list",
        "description": "The shopping list: items still to buy (id, name, quantity, unit).",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "remove_from_shopping_list",
        "description": "Remove items from the shopping list. Use list_shopping_list "
                       "first to find their ids.",
        "input_schema": {
            "type": "object",
            "properties": {"item_ids": {"type": "array", "items": {"type": "integer"}}},
            "required": ["item_ids"],
            "additionalProperties": False,
        },
    },
]

NEEDS_CONFIRMATION = set()
NOT_LOGGED = set()


def functions(data) -> dict:
    """data: services.household.UserData."""
    shopping = data.shopping
    return {
        "add_to_shopping_list": lambda a: [
            shopping.add(i["name"], i["quantity"], i["unit"]) for i in a["items"]],
        "add_recipe_to_shopping_list": lambda a: shopping.add_recipe(
            a["recipe_id"], a["servings"]),
        "list_shopping_list": lambda a: shopping.list(),
        "remove_from_shopping_list": lambda a: {
            "removed": sum(shopping.delete(item_id) for item_id in a["item_ids"])},
    }


def check(data, name: str, args: dict) -> None:
    """Nothing to check."""


def describe(data, name: str, args: dict) -> str:
    raise AssertionError("no shopping tool needs confirmation")
