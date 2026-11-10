"""The shopping list, shared by the household.

Adding an ingredient that is already on the list (same name, same unit,
not yet in the cart) adds up the quantities instead of making a new line.
"""

import sqlite3

from .recipes import Recipes, clean_ingredient
from .users import User

COLUMNS = "id, name, quantity, unit, checked, recipe_id"


class Shopping:
    def __init__(self, conn: sqlite3.Connection, user: User, recipes: Recipes):
        self.conn = conn
        self.me = user.id
        self.recipes = recipes

    def add(self, name: str, quantity: float | None = None, unit: str | None = None,
            recipe_id: int | None = None) -> dict:
        with self.conn:
            return self._add(clean_ingredient(name, quantity, unit), recipe_id)

    def add_recipe(self, recipe_id: int, servings: int | None = None) -> list[dict]:
        """Put a recipe's ingredients on the list, scaled to `servings` people."""
        recipe = self.recipes.get(recipe_id)
        if recipe is None:
            raise ValueError(f"No recipe with id {recipe_id}.")
        servings = servings or recipe["servings"]
        if not 0 < servings <= 100:
            raise ValueError("servings: 1 to 100")
        factor = servings / recipe["servings"]
        with self.conn:  # all the ingredients, or none
            return [
                self._add({**i, "quantity": scale(i["quantity"], factor)}, recipe_id)
                for i in recipe["ingredients"]
            ]

    def list(self, include_checked: bool = False) -> list[dict]:
        """Not in the cart first, then by name."""
        sql = f"SELECT {COLUMNS} FROM shopping_items"
        if not include_checked:
            sql += " WHERE checked = 0"
        sql += " ORDER BY checked, name"
        return [dict(row) for row in self.conn.execute(sql)]

    def set_checked(self, item_id: int, checked: bool) -> bool:
        with self.conn:
            cur = self.conn.execute("UPDATE shopping_items SET checked = ? WHERE id = ?",
                                    (int(checked), item_id))
        return cur.rowcount == 1

    def delete(self, item_id: int) -> bool:
        with self.conn:
            cur = self.conn.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))
        return cur.rowcount == 1

    def clear_checked(self) -> int:
        """Remove what is in the cart (after shopping). Returns how many."""
        with self.conn:
            return self.conn.execute("DELETE FROM shopping_items WHERE checked = 1").rowcount

    def _add(self, item: dict, recipe_id: int | None) -> dict:
        """Merge with the same line if there is one. Runs inside a transaction."""
        # "unit IS ?" and not "unit = ?": in SQL, NULL = NULL is not true.
        same = self.conn.execute(
            f"SELECT {COLUMNS} FROM shopping_items "
            "WHERE checked = 0 AND name = ? AND unit IS ?",
            (item["name"], item["unit"]),
        ).fetchone()
        if same is None:
            cur = self.conn.execute(
                "INSERT INTO shopping_items (name, quantity, unit, recipe_id, added_by) "
                "VALUES (?, ?, ?, ?, ?)",
                (item["name"], item["quantity"], item["unit"], recipe_id, self.me),
            )
            item_id = cur.lastrowid
        else:
            item_id = same["id"]
            if item["quantity"] is not None:  # "some tomatoes" + 3 tomatoes = 3 tomatoes
                self.conn.execute("UPDATE shopping_items SET quantity = COALESCE(quantity, 0) + ? "
                                  "WHERE id = ?", (item["quantity"], item_id))
        return dict(self.conn.execute(
            f"SELECT {COLUMNS} FROM shopping_items WHERE id = ?", (item_id,)).fetchone())


def scale(quantity: float | None, factor: float) -> float | None:
    """Quantity for another number of people, rounded to 2 decimals."""
    return None if quantity is None else round(quantity * factor, 2)
