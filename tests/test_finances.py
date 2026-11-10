"""Shared expenses: cents, shares, balances, who pays whom."""

import pytest

from assistant.services.finances import split_equally, to_cents
from assistant.services.household import open_household, user_data
from helpers import household


def test_amounts_are_exact_cents():
    assert to_cents("12,50") == 1250 and to_cents(0.1) == 10 and to_cents("7") == 700
    with pytest.raises(ValueError):  # 0.1 + 0.2 == 0.30000000000000004 in floats
        to_cents(0.1 + 0.2)
    for bad in ["0", "-5", "1.005", "abc", "1e9"]:
        with pytest.raises(ValueError):
            to_cents(bad)


def test_split_never_loses_a_cent():
    assert split_equally(1001, [1, 2], payer=2) == {2: 501, 1: 500}
    shares = split_equally(1000, [1, 2, 3], payer=1)
    assert shares == {1: 334, 2: 333, 3: 333} and sum(shares.values()) == 1000


def test_balance_and_settle_up():
    conn, me, her = household()
    mine, hers = user_data(conn, me).finances, user_data(conn, her).finances

    mine.add("80", "Courses Migros", "courses")  # 40 each: she owes me 40
    hers.add(30, "Pizza", "restaurant")  # 15 each: I owe her 15
    mine.add(20, "Son billet de train", "transport", split="for_others")  # all hers: +20
    assert {b["name"]: b["balance_cents"] for b in mine.balances()} == {
        "Grégory": 4500, "Anna": -4500}
    assert mine.settle_up() == [{"from": "Anna", "to": "Grégory", "amount_cents": 4500}]

    # She pays me back: an expense paid by her, entirely for me.
    hers.add(45, "Remboursement", "remboursement", split="for_others")
    assert mine.settle_up() == []
    assert "remboursement" not in mine.by_category()  # not spending


def test_list_shows_payer_and_for_whom():
    conn, me, her = household()
    finances = user_data(conn, me).finances
    finances.add(10, "Cinéma", "loisirs", day="2026-11-05", paid_by=her.id)
    expense = finances.list("2026-11")[0]
    assert (expense["paid_by"], expense["for_whom"]) == ("Anna", "Grégory, Anna")
    assert finances.list("2026-10") == []
    assert finances.by_category("2026-11") == {"loisirs": 1000}
    assert finances.delete(expense["id"]) and finances.list("2026-11") == []
    assert conn.execute("SELECT COUNT(*) FROM expense_shares").fetchone()[0] == 0  # CASCADE


def test_bad_expenses_are_refused():
    conn, me, _ = household()
    finances = user_data(conn, me).finances
    with pytest.raises(ValueError, match="category"):
        finances.add(10, "x", "casino")
    with pytest.raises(ValueError, match="payer"):
        finances.add(10, "x", paid_by=999)
    alone_conn, alone = open_household(":memory:", {"solo@x.com": "Solo"})
    with pytest.raises(ValueError, match="Nobody else"):
        user_data(alone_conn, alone).finances.add(10, "x", split="for_others")


def test_agent_tools_for_expenses():
    import json
    from assistant.agent.tools import ToolBox, ToolError
    conn, me, _ = household()
    asked = []
    box = ToolBox(user_data(conn, me), confirm=lambda q: asked.append(q) or True)
    expense = {"amount": 80, "description": "Courses", "category": "courses", "day": None,
               "paid_by": None, "split": "equal"}

    result = json.loads(box.run("add_expense", expense))
    assert result["amount"] == "80.00 CHF" and "amount_cents" not in result
    assert asked == ["Add «Courses» (courses), 80.00 CHF paid by Grégory, shared equally?"]
    assert json.loads(box.run("get_balance", {})) == {"to_settle": ["Anna owes Grégory 40.00 CHF"]}

    with pytest.raises(ToolError, match="Unknown person"):  # refused before asking
        box.run("add_expense", {**expense, "paid_by": "Bob"})
    with pytest.raises(ToolError, match="amount"):
        box.run("add_expense", {**expense, "amount": -3})
    assert len(asked) == 1
