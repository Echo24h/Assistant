"""Recipes tab: list, read, write or edit, import from a website, send to shopping.

The page edits ingredients as rows (quantity, unit, name): it sends them
as a list, so nothing typed has to be guessed.
"""

from ..services.recipe_import import fetch_recipe
from .api import BadRequest, SharedDB, field, id_of, query_id


class RecipesAPI:
    def __init__(self, db: SharedDB):
        self.db = db

    def get(self, user, path: str, query: dict) -> dict | None:
        if path == "/api/recipes":
            with self.db.data_for(user) as data:
                return {"recipes": data.recipes.list()}
        if path == "/api/recipes/get":
            with self.db.data_for(user) as data:
                recipe = data.recipes.get(query_id(query))
            if recipe is None:
                raise ValueError("This recipe does not exist any more.")
            return recipe
        return None

    def post(self, user, path: str, data: dict) -> dict | None:
        if path == "/api/recipes/import":
            # Download first, WITHOUT the database lock (it can take 10 s).
            recipe = fetch_recipe(field(data, "url", str))
            with self.db.data_for(user) as mine:
                return mine.recipes.add_imported(recipe)

        with self.db.data_for(user) as mine:
            if path == "/api/recipes/add":
                return mine.recipes.add(
                    field(data, "title", str),
                    field(data, "servings", int),
                    ingredient_rows(data),
                    field(data, "instructions", str, optional=True) or "",
                )
            if path == "/api/recipes/update":  # the page sends the whole recipe
                return mine.recipes.update(
                    id_of(data),
                    field(data, "title", str),
                    field(data, "servings", int),
                    ingredient_rows(data),
                    field(data, "instructions", str, optional=True) or "",
                )
            if path == "/api/recipes/delete":
                return {"ok": mine.recipes.delete(id_of(data))}
            if path == "/api/recipes/shop":
                items = mine.shopping.add_recipe(id_of(data),
                                                 field(data, "servings", int, optional=True))
                return {"added": len(items)}
        return None


def ingredient_row(row) -> dict:
    """{"name": "Pâtes", "quantity": 400, "unit": "g"}: the shape only (types).
    Shared with the shopping tab, which adds one row at a time."""
    if not isinstance(row, dict):
        raise BadRequest("ingredients: a list of {name, quantity, unit}")
    return {"name": field(row, "name", str),
            "quantity": number(row.get("quantity")),
            "unit": field(row, "unit", str, optional=True)}


def ingredient_rows(data: dict) -> list[dict]:
    """[{"name": "pâtes", "quantity": 400, "unit": "g"}, ...] as sent by the page.
    Only the shape is checked here; the rules are in services/recipes.py."""
    return [ingredient_row(row) for row in field(data, "ingredients", list)]


def number(value) -> float | None:
    """A quantity: a number or null (True/False are not numbers here)."""
    if value is None:
        return None
    if type(value) not in (int, float):
        raise BadRequest("quantity: a number or null")
    return value
