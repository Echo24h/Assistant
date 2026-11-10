"""Recipes, shared by the household.

A recipe is written for a number of servings; its ingredients have an
optional quantity and unit. Units are normalized (kg -> g, l -> ml...) so
that the shopping list can add up the same ingredient from two recipes.
"""

import re
import sqlite3

from .users import User

MAX_TITLE = 200
MAX_INGREDIENTS = 100
MAX_INSTRUCTIONS = 20_000

# Unit written -> (unit stored, factor). Anything else is kept as written.
UNITS = {
    "g": ("g", 1), "gr": ("g", 1), "gramme": ("g", 1), "grammes": ("g", 1),
    "kg": ("g", 1000),
    "ml": ("ml", 1), "cl": ("ml", 10), "dl": ("ml", 100), "l": ("ml", 1000),
    "c. à café": ("tsp", 1), "cc": ("tsp", 1), "cuillère à café": ("tsp", 1), "tsp": ("tsp", 1),
    "c. à soupe": ("tbsp", 1), "cs": ("tbsp", 1), "cuillère à soupe": ("tbsp", 1),
    "tbsp": ("tbsp", 1),
    "pièce": (None, 1), "pièces": (None, 1), "piece": (None, 1), "pieces": (None, 1),
}


# How a stored unit is written back for people (and read again by UNITS).
SPOKEN_UNITS = {"tsp": "c. à café", "tbsp": "c. à soupe"}

NUMBER = re.compile(r"^\s*(\d+/\d+|\d+(?:[.,]\d+)?|[½¼¾])\s*")
FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75}


def parse_ingredient_line(line: str) -> dict:
    """"500 g de pâtes" -> {"name": "pâtes", "quantity": 500, "unit": "g"}.

    Used by the web page (typed lines) and the URL import (websites give
    ingredients as text). No model: 0 tokens, always the same result.
    """
    text, quantity, unit = line.strip(), None, None
    number = NUMBER.match(text)
    if number:
        quantity, text = to_number(number.group(1)), text[number.end():]
        lower = text.lower()
        for word in sorted(UNITS, key=len, reverse=True):  # "c. à soupe" before "cs"
            if lower.startswith(word + " "):
                unit, text = word, text[len(word):]
                break
    text = re.sub(r"^(de |d'|d’)", "", text.strip(), flags=re.IGNORECASE)
    return clean_ingredient(text, quantity, unit)


def to_number(text: str) -> float:
    if text in FRACTIONS:
        return FRACTIONS[text]
    if "/" in text:
        top, bottom = text.split("/")
        if int(bottom) == 0:
            raise ValueError(f"bad quantity: {text}")
        return int(top) / int(bottom)
    return float(text.replace(",", "."))


def clean_ingredient(name: str, quantity: float | None, unit: str | None) -> dict:
    """Check one ingredient and normalize it: {"name", "quantity", "unit"}."""
    name = name.strip().lower()
    if not 0 < len(name) <= 100:
        raise ValueError("ingredient name: 1 to 100 characters")
    if quantity is not None and not quantity > 0:
        raise ValueError(f"quantity of {name}: positive, or null")
    unit = (unit or "").strip().lower() or None
    if unit is not None and len(unit) > 20:
        raise ValueError(f"unit of {name}: 20 characters at most")
    if unit in UNITS:
        unit, factor = UNITS[unit]
        if quantity is not None:
            quantity = quantity * factor
    return {"name": name, "quantity": quantity, "unit": unit}


def check_recipe(title: str, servings: int, ingredients: list[dict],
                 instructions: str) -> tuple[str, list[dict]]:
    """The rules of a recipe, for adding and changing: (clean title, clean ingredients)."""
    title = title.strip()
    if not 0 < len(title) <= MAX_TITLE:
        raise ValueError(f"title: 1 to {MAX_TITLE} characters")
    if not 0 < servings <= 100:
        raise ValueError("servings: 1 to 100")
    if not 0 < len(ingredients) <= MAX_INGREDIENTS:
        raise ValueError(f"ingredients: 1 to {MAX_INGREDIENTS}")
    if len(instructions) > MAX_INSTRUCTIONS:
        raise ValueError(f"instructions: {MAX_INSTRUCTIONS} characters at most")
    items = [clean_ingredient(i["name"], i.get("quantity"), i.get("unit")) for i in ingredients]
    return title, items


def ingredient_line(item: dict) -> str:
    """The opposite of parse_ingredient_line: {500, "g", "pâtes"} -> "500 g pâtes".
    Used to edit a recipe as text; reading the line back gives the same item."""
    quantity = item["quantity"]
    if quantity is None:
        return item["name"]
    number = f"{quantity:.2f}".rstrip("0").rstrip(".")  # 500.0 -> "500", 0.5 -> "0.5"
    unit = SPOKEN_UNITS.get(item["unit"], item["unit"])
    return f"{number} {unit} {item['name']}" if unit else f"{number} {item['name']}"


class Recipes:
    def __init__(self, conn: sqlite3.Connection, user: User):
        self.conn = conn
        self.me = user.id

    def add(self, title: str, servings: int, ingredients: list[dict],
            instructions: str = "", source_url: str | None = None) -> dict:
        """ingredients: [{"name", "quantity", "unit"}] (quantity and unit may be None)."""
        title, items = check_recipe(title, servings, ingredients, instructions)
        with self.conn:  # the recipe and all its ingredients, or nothing
            cur = self.conn.execute(
                "INSERT INTO recipes (title, servings, instructions, source_url, created_by) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, servings, instructions.strip(), source_url, self.me),
            )
            self._insert_ingredients(cur.lastrowid, items)
        return self.get(cur.lastrowid)

    def update(self, recipe_id: int, title: str | None = None, servings: int | None = None,
               ingredients: list[dict] | None = None,
               instructions: str | None = None) -> dict:
        """Change a recipe. None = keep as it is. New ingredients replace the
        old ones (all of them: the list is given in full)."""
        current = self.get(recipe_id)
        if current is None:
            raise ValueError(f"No recipe with id {recipe_id}.")
        title = current["title"] if title is None else title
        servings = current["servings"] if servings is None else servings
        instructions = current["instructions"] if instructions is None else instructions
        title, items = check_recipe(title, servings,
                                    current["ingredients"] if ingredients is None else ingredients,
                                    instructions)
        with self.conn:  # the recipe and its new ingredients, or nothing
            self.conn.execute(
                "UPDATE recipes SET title = ?, servings = ?, instructions = ? WHERE id = ?",
                (title, servings, instructions.strip(), recipe_id),
            )
            if ingredients is not None:
                self.conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?",
                                  (recipe_id,))
                self._insert_ingredients(recipe_id, items)
        return self.get(recipe_id)

    def _insert_ingredients(self, recipe_id: int, items: list[dict]) -> None:
        """Runs inside the caller's transaction."""
        self.conn.executemany(
            "INSERT INTO recipe_ingredients (recipe_id, position, name, quantity, unit) "
            "VALUES (?, ?, ?, ?, ?)",
            [(recipe_id, n, i["name"], i["quantity"], i["unit"]) for n, i in enumerate(items)],
        )

    def list(self, search: str | None = None) -> list[dict]:
        """Titles only (short = fewer tokens). search: part of the title."""
        sql, params = "SELECT id, title, servings FROM recipes", []
        if search:
            sql += " WHERE title LIKE ?"
            params.append(f"%{search.strip()}%")
        sql += " ORDER BY title COLLATE NOCASE"
        return [dict(row) for row in self.conn.execute(sql, params)]

    def get(self, recipe_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT id, title, servings, instructions, source_url FROM recipes WHERE id = ?",
            (recipe_id,),
        ).fetchone()
        if row is None:
            return None
        recipe = dict(row)
        recipe["ingredients"] = [dict(i) for i in self.conn.execute(
            "SELECT name, quantity, unit FROM recipe_ingredients "
            "WHERE recipe_id = ? ORDER BY position", (recipe_id,))]
        return recipe

    def delete(self, recipe_id: int) -> bool:
        with self.conn:
            cur = self.conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        return cur.rowcount == 1
