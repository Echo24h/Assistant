"""Shared expenses and "who owes whom", entered by hand (no bank access).

Money is stored in cents (integers): 0.1 + 0.2 != 0.3 with floats.
Each expense has a payer and shares (expense_shares) that add up to the
amount. A person's balance = what they paid - the sum of their shares:
positive, the others owe them; negative, they owe.
A repayment is just an expense paid by one, entirely for the other.
"""

import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation

from .users import User, list_users

CATEGORIES = ("courses", "loyer", "factures", "restaurant", "transport", "maison",
              "loisirs", "santé", "cadeaux", "voyage", "remboursement", "autre")
SPLITS = ("equal", "for_others")  # 50/50, or paid for the other person(s)


def to_cents(amount) -> int:
    """12.5 / "12,50" / "12.50" -> 1250. Refuses 0, negatives and 0.001."""
    try:
        value = Decimal(str(amount).replace(",", ".").strip())
    except InvalidOperation:
        raise ValueError(f"Not an amount: {amount}") from None
    cents = value * 100
    if cents != cents.to_integral_value() or not 0 < cents <= 10_000_000:
        raise ValueError("amount: positive, at most 2 decimals, at most 100'000")
    return int(cents)


def split_equally(amount: int, people: list[int], payer: int) -> dict[int, int]:
    """Shares in cents adding up exactly to `amount`. 1001 cents for 2 people:
    501 for the payer, 500 for the other (the cent left goes to the payer)."""
    base, left = divmod(amount, len(people))
    ordered = sorted(people, key=lambda p: p != payer)  # payer first
    return {p: base + (1 if n < left else 0) for n, p in enumerate(ordered)}


def money(cents: int, currency: str) -> str:
    """4550 -> "45.50 CHF" (for people and the model: never raw cents)."""
    return f"{cents // 100}.{cents % 100:02d} {currency}"


class Finances:
    def __init__(self, conn: sqlite3.Connection, user: User, currency: str = "CHF"):
        self.conn = conn
        self.me = user.id
        self.currency = currency

    def people(self) -> list[User]:
        return list_users(self.conn)

    def add(self, amount, description: str, category: str = "autre",
            day: str | None = None, paid_by: int | None = None,
            split: str = "equal") -> dict:
        cents = to_cents(amount)
        description = description.strip()
        if not 0 < len(description) <= 200:
            raise ValueError("description: 1 to 200 characters")
        if category not in CATEGORIES:
            raise ValueError(f"category: one of {', '.join(CATEGORIES)}")
        if split not in SPLITS:
            raise ValueError(f"split: one of {', '.join(SPLITS)}")
        day = day or date.today().isoformat()
        date.fromisoformat(day)
        everyone = [p.id for p in self.people()]
        payer = paid_by or self.me
        if payer not in everyone:
            raise ValueError("The payer is not in the household.")
        others = [p for p in everyone if p != payer]
        if split == "for_others" and not others:
            raise ValueError("Nobody else in the household.")
        if split == "equal":
            shares = split_equally(cents, everyone, payer)
        else:
            shares = split_equally(cents, others, others[0])
        assert sum(shares.values()) == cents  # never lose or invent a cent

        with self.conn:  # the expense and its shares, or nothing
            cur = self.conn.execute(
                "INSERT INTO expenses (day, description, category, amount_cents, paid_by, "
                "created_by) VALUES (?, ?, ?, ?, ?, ?)",
                (day, description, category, cents, payer, self.me),
            )
            self.conn.executemany(
                "INSERT INTO expense_shares (expense_id, user_id, amount_cents) VALUES (?, ?, ?)",
                [(cur.lastrowid, person, share) for person, share in shares.items()],
            )
        return self.get(cur.lastrowid)

    def get(self, expense_id: int) -> dict | None:
        rows = self._list_where("e.id = ?", (expense_id,))
        return rows[0] if rows else None

    def list(self, month: str | None = None) -> list[dict]:
        """Expenses of a month ("2026-11"), the current one by default, newest first."""
        month = month or date.today().isoformat()[:7]
        date.fromisoformat(month + "-01")  # checks the format
        return self._list_where("e.day LIKE ?", (month + "-%",))

    def _list_where(self, condition: str, params: tuple) -> list[dict]:
        """`condition` is always written in this file, never user input."""
        rows = self.conn.execute(
            "SELECT e.id, e.day, e.description, e.category, e.amount_cents, "
            "u.name AS paid_by, "
            # The people this expense is for (share > 0), e.g. "Grégory, Anna".
            "(SELECT group_concat(s_u.name, ', ') FROM expense_shares s "
            " JOIN users s_u ON s_u.id = s.user_id "
            " WHERE s.expense_id = e.id AND s.amount_cents > 0) AS for_whom "
            f"FROM expenses e JOIN users u ON u.id = e.paid_by WHERE {condition} "
            "ORDER BY e.day DESC, e.id DESC",
            params,
        )
        return [dict(row) for row in rows]

    def delete(self, expense_id: int) -> bool:
        with self.conn:  # the shares go too (ON DELETE CASCADE)
            cur = self.conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        return cur.rowcount == 1

    def balances(self) -> list[dict]:
        """Each person: paid - owed, over all time. The total is always 0."""
        rows = self.conn.execute(
            "SELECT u.id, u.name, "
            " COALESCE((SELECT SUM(amount_cents) FROM expenses WHERE paid_by = u.id), 0) "
            " - COALESCE((SELECT SUM(amount_cents) FROM expense_shares WHERE user_id = u.id), 0)"
            " AS balance_cents "
            "FROM users u ORDER BY u.id"
        )
        return [dict(row) for row in rows]

    def settle_up(self) -> list[dict]:
        """Who should pay whom to be even: [{"from", "to", "amount_cents"}].

        The person who owes the most pays the one who is owed the most,
        until everyone is at 0 (for two people: a single payment).
        """
        owed = {b["name"]: b["balance_cents"] for b in self.balances() if b["balance_cents"]}
        payments = []
        while owed:
            debtor = min(owed, key=owed.get)  # most negative
            creditor = max(owed, key=owed.get)  # most positive
            amount = min(-owed[debtor], owed[creditor])
            payments.append({"from": debtor, "to": creditor, "amount_cents": amount})
            owed[debtor] += amount
            owed[creditor] -= amount
            owed = {name: cents for name, cents in owed.items() if cents}
        return payments

    def by_category(self, month: str | None = None) -> dict[str, int]:
        """Total spent per category in a month (repayments are not spending)."""
        totals: dict[str, int] = {}
        for expense in self.list(month):
            if expense["category"] != "remboursement":
                totals[expense["category"]] = (totals.get(expense["category"], 0)
                                               + expense["amount_cents"])
        return dict(sorted(totals.items(), key=lambda item: -item[1]))
