"""Product tool (services/products.py): the catalog is written by the developer.

Ingredients and shopping items must be known products; the other tools
refuse an unknown name with close suggestions. If none fits, the agent can
ask the developer to add the product.
"""

DEFINITIONS = [
    {
        "name": "request_product",
        "description": "Ask the developer to add a product to the catalog, when an "
                       "ingredient or a shopping item is refused as unknown and no "
                       "suggested name fits. Tell the user it was requested.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "e.g. 'Tahini'"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
]

NEEDS_CONFIRMATION = set()  # harmless: a note for the developer
NOT_LOGGED = set()


def functions(data) -> dict:
    """data: services.household.UserData."""
    return {"request_product": lambda a: data.products.request(a["name"], data.user.id)}


def check(data, name: str, args: dict) -> None:
    """Nothing to check."""


def describe(data, name: str, args: dict) -> str:
    raise AssertionError("request_product needs no confirmation")
