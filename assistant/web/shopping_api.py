"""Shopping tab: the shared list, used in the shop (services/shopping.py)."""

from ..services.recipes import parse_ingredient_line
from .api import SharedDB, field, id_of


class ShoppingAPI:
    def __init__(self, db: SharedDB):
        self.db = db

    def get(self, user, path: str, query: dict) -> dict | None:
        if path == "/api/shopping":
            with self.db.data_for(user) as data:
                return {"items": data.shopping.list(include_checked=True)}
        return None

    def post(self, user, path: str, data: dict) -> dict | None:
        with self.db.data_for(user) as mine:
            shopping = mine.shopping
            if path == "/api/shopping/add":  # one typed line: "2 l de lait"
                item = parse_ingredient_line(field(data, "text", str))
                return shopping.add(item["name"], item["quantity"], item["unit"])
            if path == "/api/shopping/check":
                return {"ok": shopping.set_checked(id_of(data), field(data, "checked", bool))}
            if path == "/api/shopping/delete":
                return {"ok": shopping.delete(id_of(data))}
            if path == "/api/shopping/clear":
                return {"removed": shopping.clear_checked()}
        return None
