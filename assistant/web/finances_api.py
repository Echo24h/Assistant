"""Finances tab: shared expenses and who owes whom (services/finances.py)."""

from ..services.finances import CATEGORIES, money
from .api import SharedDB, field, id_of


class FinancesAPI:
    def __init__(self, db: SharedDB):
        self.db = db

    def get(self, user, path: str, query: dict) -> dict | None:
        if path != "/api/finances":
            return None
        with self.db.data_for(user) as data:
            finances, month = data.finances, query.get("month") or None
            show = lambda cents: money(cents, finances.currency)
            return {
                "me": user.name,
                "people": [{"id": p.id, "name": p.name} for p in finances.people()],
                "categories": list(CATEGORIES),
                "settle": [{"from": s["from"], "to": s["to"], "amount": show(s["amount_cents"])}
                           for s in finances.settle_up()],
                "expenses": [{**e, "amount": show(e["amount_cents"])}
                             for e in finances.list(month)],
                "by_category": {c: show(cents) for c, cents in finances.by_category(month).items()},
            }

    def post(self, user, path: str, data: dict) -> dict | None:
        with self.db.data_for(user) as mine:
            if path == "/api/finances/add":
                return mine.finances.add(
                    field(data, "amount", str),  # typed text, e.g. "12,50"
                    field(data, "description", str),
                    field(data, "category", str),
                    field(data, "day", str, optional=True) or None,
                    field(data, "paid_by", int, optional=True),
                    field(data, "split", str),
                )
            if path == "/api/finances/delete":
                return {"ok": mine.finances.delete(id_of(data))}
        return None
