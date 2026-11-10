"""Products: the names for the suggestions, and "please add this product".

The catalog itself is written by the developer (assistant/data/products.toml):
nothing here can add a product, only ask for one.
"""

from .api import SharedDB, field


class ProductsAPI:
    def __init__(self, db: SharedDB):
        self.db = db

    def get(self, user, path: str, query: dict) -> dict | None:
        if path == "/api/products":
            with self.db.data_for(user) as data:
                return {"products": data.products.names()}
        return None

    def post(self, user, path: str, data: dict) -> dict | None:
        if path == "/api/products/request":
            with self.db.data_for(user) as mine:
                return mine.products.request(field(data, "name", str), user.id)
        return None
