"""Recipes tab: list, read, type in, import from a website, send to shopping."""

from ..services.recipe_import import fetch_recipe
from ..services.recipes import parse_ingredient_line
from .api import SharedDB, field, id_of, query_id


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
                return mine.recipes.add(**recipe)

        with self.db.data_for(user) as mine:
            if path == "/api/recipes/add":
                # Ingredients typed one per line: "500 g de pâtes".
                lines = field(data, "ingredients", str).splitlines()
                return mine.recipes.add(
                    field(data, "title", str),
                    field(data, "servings", int),
                    [parse_ingredient_line(line) for line in lines if line.strip()],
                    field(data, "instructions", str, optional=True) or "",
                )
            if path == "/api/recipes/delete":
                return {"ok": mine.recipes.delete(id_of(data))}
            if path == "/api/recipes/shop":
                items = mine.shopping.add_recipe(id_of(data),
                                                 field(data, "servings", int, optional=True))
                return {"added": len(items)}
        return None
