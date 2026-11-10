"""Everything one person can read and change, in one object.

Built once per conversation (agent) or per request (web page). Each domain
filters by this user, so the code above never has to think about it.
Domains: tasks, products, recipes, shopping, finances, bugs.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .bugs import Bugs
from .db import connect
from .finances import Finances
from .products import Products, catalog
from .recipes import Recipes
from .shopping import Shopping
from .tasks import Tasks
from .users import User, sync_users


def open_household(path: Path | str, people: dict[str, str], language: str = "fr"):
    """Open and upgrade the database; the people follow .env and the products
    follow assistant/data/products.toml. Return (conn, owner)."""
    conn = connect(path)
    owner = sync_users(conn, people)
    Products(conn, catalog(), language).sync()
    return conn, owner


@dataclass(frozen=True)
class UserData:
    conn: sqlite3.Connection
    user: User
    tasks: Tasks
    recipes: Recipes
    products: Products
    shopping: Shopping
    finances: Finances
    bugs: Bugs

    def close(self) -> None:
        """Close the connection, when this data has its own (app.build_agent)."""
        self.conn.close()


def user_data(conn: sqlite3.Connection, user: User, currency: str = "CHF",
              language: str = "fr") -> UserData:
    """language: code of the product names ("fr"), see products.language_code."""
    products = Products(conn, catalog(), language)
    recipes = Recipes(conn, user, products)
    return UserData(
        conn=conn, user=user,
        tasks=Tasks(conn, user),
        products=products,
        recipes=recipes,
        shopping=Shopping(conn, user, recipes, products),
        finances=Finances(conn, user, currency),
        bugs=Bugs(conn, user),
    )
