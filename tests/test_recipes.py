"""Recipes and the shopping list (services only)."""

import pytest

from helpers import household
from assistant.services.household import user_data

PASTA = [
    {"name": "Pâtes", "quantity": 0.5, "unit": "kg"},
    {"name": "Tomate", "quantity": 4, "unit": None},
    {"name": "Sel", "quantity": None, "unit": None},
]


@pytest.fixture
def data():
    conn, me, _ = household()
    return user_data(conn, me)


def test_recipe_is_stored_normalized(data):
    recipe = data.recipes.add("Pâtes tomate", 2, PASTA, "Cuire les pâtes.")
    assert recipe["ingredients"] == [
        {"name": "pâtes", "quantity": 500, "unit": "g"},  # kg -> g, lowercase
        {"name": "tomate", "quantity": 4, "unit": None},
        {"name": "sel", "quantity": None, "unit": None},
    ]
    assert data.recipes.list("tomate") == [{"id": recipe["id"], "title": "Pâtes tomate",
                                            "servings": 2}]


def test_bad_recipes_are_refused(data):
    with pytest.raises(ValueError, match="ingredients"):
        data.recipes.add("Empty", 2, [])
    with pytest.raises(ValueError, match="servings"):
        data.recipes.add("Zero", 0, PASTA)
    with pytest.raises(ValueError, match="quantity"):
        data.recipes.add("Negative", 2, [{"name": "x", "quantity": -1, "unit": None}])


def test_recipe_to_shopping_list_scales_and_merges(data):
    recipe = data.recipes.add("Pâtes tomate", 2, PASTA)
    data.shopping.add("tomate", 1)  # already on the list
    data.shopping.add_recipe(recipe["id"], servings=4)  # for 4 people: x2

    items = {i["name"]: i for i in data.shopping.list()}
    assert items["pâtes"]["quantity"] == 1000 and items["pâtes"]["unit"] == "g"
    assert items["tomate"]["quantity"] == 9  # 1 + 4 x 2: one line, not two
    assert items["sel"]["quantity"] is None
    assert len(items) == 3


def test_merge_only_same_unit_and_not_in_cart(data):
    milk = data.shopping.add("lait", 1, "l")
    data.shopping.add("lait", 50, "cl")  # cl -> ml, same unit as l -> ml
    assert data.shopping.list()[0]["quantity"] == 1500
    data.shopping.add("lait", 2, None)  # 2 bottles: another unit, another line
    assert len(data.shopping.list()) == 2

    data.shopping.set_checked(milk["id"], True)  # in the cart
    data.shopping.add("lait", 1, "l")  # a new line, the cart is not changed
    assert len(data.shopping.list()) == 2 and len(data.shopping.list(True)) == 3
    assert data.shopping.clear_checked() == 1


def test_shopping_list_is_shared_and_survives_recipe_deletion():
    conn, me, her = household()
    recipe = user_data(conn, me).recipes.add("Pâtes tomate", 2, PASTA)
    user_data(conn, me).shopping.add_recipe(recipe["id"])

    hers = user_data(conn, her)
    assert len(hers.shopping.list()) == 3  # shared by the household
    assert hers.recipes.delete(recipe["id"])  # she can delete a shared recipe
    assert len(hers.shopping.list()) == 3  # the list is kept (ON DELETE SET NULL)
    assert conn.execute("SELECT COUNT(*) FROM recipe_ingredients").fetchone()[0] == 0  # CASCADE


def test_agent_tools_for_recipes_and_shopping(data):
    from assistant.agent.tools import ToolBox, ToolError
    asked = []
    box = ToolBox(data, confirm=lambda q: asked.append(q) or True)
    box.run("save_recipe", {"title": "Pâtes tomate", "servings": 2,
                            "ingredients": PASTA, "instructions": "1. Cuire."})
    assert asked == ["Save the recipe «Pâtes tomate» (2 people: Pâtes, Tomate, Sel)?"]

    recipe_id = data.recipes.list()[0]["id"]
    box.run("add_recipe_to_shopping_list", {"recipe_id": recipe_id, "servings": None})
    box.run("add_to_shopping_list", {"items": [{"name": "Pain", "quantity": None, "unit": None}]})
    assert len(data.shopping.list()) == 4 and len(asked) == 1  # no confirmation for the list

    with pytest.raises(ToolError, match="No recipe"):
        box.run("get_recipe", {"recipe_id": 999})
