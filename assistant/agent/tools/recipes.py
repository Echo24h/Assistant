"""Recipe tools (services/recipes.py). Recipes are shared by the household."""

INGREDIENTS = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Singular, e.g. 'tomato'."},
            "quantity": {"type": ["number", "null"], "description": "null = 'some' (salt)."},
            "unit": {"type": ["string", "null"],
                     "description": "g, ml, tsp, tbsp... null = pieces."},
        },
        "required": ["name", "quantity", "unit"],
        "additionalProperties": False,
    },
}
RECIPE_ID = {"type": "object", "properties": {"recipe_id": {"type": "integer"}},
             "required": ["recipe_id"], "additionalProperties": False}

DEFINITIONS = [
    {
        "name": "save_recipe",
        "description": "Save a recipe (dictated by the user, or one you suggested and "
                       "the user wants to keep). The user is asked to confirm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "servings": {"type": "integer", "description": "Number of people."},
                "ingredients": INGREDIENTS,
                "instructions": {"type": "string", "description": "Short numbered steps."},
            },
            "required": ["title", "servings", "ingredients", "instructions"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_recipes",
        "description": "List saved recipes (id, title, servings).",
        "input_schema": {
            "type": "object",
            "properties": {"search": {"type": ["string", "null"],
                                      "description": "Part of the title, or null for all."}},
            "required": ["search"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_recipe",
        "description": "A saved recipe with its ingredients and instructions.",
        "input_schema": RECIPE_ID,
    },
    {
        "name": "delete_recipe",
        "description": "Delete a saved recipe. The user is asked to confirm.",
        "input_schema": RECIPE_ID,
    },
]

NEEDS_CONFIRMATION = {"save_recipe", "delete_recipe"}
NOT_LOGGED = set()


def functions(data) -> dict:
    """data: services.household.UserData."""
    return {
        "save_recipe": lambda a: data.recipes.add(
            a["title"], a["servings"], a["ingredients"], a["instructions"]),
        "list_recipes": lambda a: data.recipes.list(a.get("search")),
        "get_recipe": lambda a: get_recipe(data, a["recipe_id"]),
        "delete_recipe": lambda a: delete_recipe(data, a["recipe_id"]),
    }


def get_recipe(data, recipe_id: int) -> dict:
    recipe = data.recipes.get(recipe_id)
    if recipe is None:
        raise ValueError(f"No recipe with id {recipe_id}.")
    return recipe


def delete_recipe(data, recipe_id: int) -> dict:
    if not data.recipes.delete(recipe_id):
        raise ValueError(f"No recipe with id {recipe_id}.")
    return {"ok": True}


def check(data, name: str, args: dict) -> None:
    """Nothing to check before confirmation."""


def describe(data, name: str, args: dict) -> str:
    if name == "save_recipe":
        names = ", ".join(i["name"] for i in args["ingredients"][:6])
        more = "…" if len(args["ingredients"]) > 6 else ""
        return f"Save the recipe «{args['title']}» ({args['servings']} people: {names}{more})?"
    recipe = data.recipes.get(args["recipe_id"])
    label = recipe["title"] if recipe else f"#{args['recipe_id']} (not found)"
    return f"Delete the recipe «{label}»?"
