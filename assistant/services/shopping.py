"""The shopping list, shared by the household.

Adding a product that is already on the list (same product, same unit,
not yet in the cart) adds up the quantities instead of making a new line.
The list is sorted by shop aisle (aisles come from services/products.py).
"""

import sqlite3

from .products import Products, aisle_order
from .recipes import Recipes, clean_ingredient
from .users import User

# A shopping line with its product's name and aisle (s = shopping_items).
SELECT = ("SELECT s.id, p.name, p.aisle, s.quantity, s.unit, s.checked, s.recipe_id "
          "FROM shopping_items s JOIN products p ON p.id = s.product_id")


class Shopping:
    def __init__(self, conn: sqlite3.Connection, user: User, recipes: Recipes,
                 products: Products):
        self.conn = conn
        self.me = user.id
        self.recipes = recipes
        self.products = products

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
        """Not in the cart first, then in the order of the shop's aisles."""
        sql = SELECT
        if not include_checked:
            sql += " WHERE s.checked = 0"
        sql += f" ORDER BY s.checked, {aisle_order('p.aisle')}, p.name"
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
        product_id = self.products.id_for(item["name"])  # strict: unknown -> ValueError
        same = self.conn.execute(
            "SELECT id FROM shopping_items WHERE checked = 0 AND product_id = ? AND unit IS ?",
            (product_id, item["unit"]),
        ).fetchone()
        if same is None:
            cur = self.conn.execute(
                "INSERT INTO shopping_items (product_id, quantity, unit, recipe_id, added_by) "
                "VALUES (?, ?, ?, ?, ?)",
                (product_id, item["quantity"], item["unit"], recipe_id, self.me),
            )
            item_id = cur.lastrowid
        else:
            item_id = same["id"]
            if item["quantity"] is not None:  # "some tomatoes" + 3 tomatoes = 3 tomatoes
                self.conn.execute("UPDATE shopping_items SET quantity = COALESCE(quantity, 0) + ? "
                                  "WHERE id = ?", (item["quantity"], item_id))
        return dict(self.conn.execute(f"{SELECT} WHERE s.id = ?", (item_id,)).fetchone())


def scale(quantity: float | None, factor: float) -> float | None:
    """Quantity for another number of people, rounded to 2 decimals."""
    return None if quantity is None else round(quantity * factor, 2)
