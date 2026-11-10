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
                       "the user wants to keep). Copy it faithfully: the same product "
                       "may appear several times (eggs for the dough, yolks for the "
                       "cream): never merge lines, never change quantities or steps. "
                       "The user is asked to confirm.",
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
        "name": "update_recipe",
        "description": "Change a saved recipe. null = keep as it is. Use get_recipe "
                       "first: new ingredients REPLACE all the old ones, so give the "
                       "full list. Change only what the user asked. The user is asked "
                       "to confirm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe_id": {"type": "integer"},
                "title": {"type": ["string", "null"]},
                "servings": {"type": ["integer", "null"]},
                "ingredients": {**INGREDIENTS, "type": ["array", "null"]},
                "instructions": {"type": ["string", "null"]},
            },
            "required": ["recipe_id", "title", "servings", "ingredients", "instructions"],
            "additionalProperties": False,
        },
    },
    {
        "name": "delete_recipe",
        "description": "Delete a saved recipe. The user is asked to confirm.",
        "input_schema": RECIPE_ID,
    },
]

NEEDS_CONFIRMATION = {"save_recipe", "update_recipe", "delete_recipe"}
NOT_LOGGED = set()


def functions(data) -> dict:
    """data: services.household.UserData."""
    return {
        "save_recipe": lambda a: data.recipes.add(
            a["title"], a["servings"], a["ingredients"], a["instructions"]),
        "list_recipes": lambda a: data.recipes.list(a.get("search")),
        "get_recipe": lambda a: get_recipe(data, a["recipe_id"]),
        "update_recipe": lambda a: data.recipes.update(
            a["recipe_id"], a["title"], a["servings"], a["ingredients"], a["instructions"]),
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
    """Refuse unknown products BEFORE asking the user: otherwise they say yes,
    the save fails, the model fixes the names and asks a second time."""
    if name in ("save_recipe", "update_recipe") and args.get("ingredients"):
        data.products.check_known([i["name"] for i in args["ingredients"]])


def amounts(ingredients: list[dict]) -> str:
    """"Œuf 4, Lait 500 ml, Sel": every line with its quantity, so that the
    user can see a wrong quantity BEFORE saying yes (it happened: 12 eggs)."""
    def one(i):
        quantity = "" if i["quantity"] is None else f" {i['quantity']:g}"
        unit = f" {i['unit']}" if i["unit"] and i["quantity"] is not None else ""
        return f"{i['name']}{quantity}{unit}"
    return ", ".join(one(i) for i in ingredients)


def describe(data, name: str, args: dict) -> str:
    if name == "save_recipe":
        return (f"Save the recipe «{args['title']}» for {args['servings']} people: "
                f"{amounts(args['ingredients'])}?")
    recipe = data.recipes.get(args["recipe_id"])
    label = recipe["title"] if recipe else f"#{args['recipe_id']} (not found)"
    if name == "update_recipe":
        changes = []
        if args["title"] is not None:
            changes.append(f"title → «{args['title']}»")
        if args["servings"] is not None:
            changes.append(f"{args['servings']} people")
        if args["ingredients"] is not None:
            changes.append(f"ingredients → {amounts(args['ingredients'])}")
        if args["instructions"] is not None:
            changes.append("new steps")
        return f"Change the recipe «{label}»: {'; '.join(changes) or 'nothing'}?"
    return f"Delete the recipe «{label}»?"
