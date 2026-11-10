"""The product catalog (assistant/data/products.toml): strict, synced, safe."""

import sqlite3

import pytest

from assistant.services.db import MIGRATIONS_DIR
from assistant.services.household import open_household, user_data
from assistant.services.products import catalog, read_catalog
from helpers import household


@pytest.mark.parametrize("written, key", [
    ("Tomates", "tomato"), ("epinards", "spinach"), ("Œufs", "egg"), ("oeuf", "egg"),
    ("gousses d’ail", "garlic"), ("Spaghetti", "pasta"), ("pâtes (spaghetti)", "pasta"),
    ("papier toillette", "toilet_paper"), ("bœuf haché", "ground_beef"), ("riz", "rice"),
    ("noix", "walnut"), ("tomates concassées", "crushed_tomatoes"),
])
def test_names_find_their_product(written, key):
    assert catalog().find(written).key == key


def test_unknown_names_are_not_guessed():
    for written in ["pierre", "tomat", "zaatar", ""]:
        assert catalog().find(written) is None
    assert catalog().closest("tomat", "fr") == ["Tomate"]  # names only, not English keys


def test_mistakes_in_the_file_stop_the_start(tmp_path):
    file = tmp_path / "products.toml"
    file.write_text('[tomato]\nfr = "Tomate"\naisle = "fruits et légumes"\n'
                    '[tomato2]\nfr = "Tomates"\naisle = "fruits et légumes"\n')
    with pytest.raises(ValueError, match="both tomato and tomato2"):
        read_catalog(file)
    file.write_text('[tomato]\nfr = "Tomate"\naisle = "rayon secret"\n')
    with pytest.raises(ValueError, match="aisle"):
        read_catalog(file)
    file.write_text('[Tomato]\nfr = "Tomate"\naisle = "autre"\n')
    with pytest.raises(ValueError, match="key"):
        read_catalog(file)


@pytest.fixture
def data():
    conn, me, _ = household()
    return user_data(conn, me)


def test_strict_everywhere_with_all_problems_at_once(data):
    rows = [{"name": "tomates", "quantity": 2, "unit": None},
            {"name": "pierre", "quantity": 1, "unit": None},
            {"name": "tomat", "quantity": 1, "unit": None}]
    with pytest.raises(ValueError) as error:
        data.recipes.add("Soupe", 2, rows)
    assert '"pierre"' in str(error.value) and '"tomat" (close: Tomate' in str(error.value)
    assert data.recipes.list() == []  # nothing saved
    with pytest.raises(ValueError, match="Unknown product"):
        data.shopping.add("pierre")


def test_import_keeps_unknown_ingredients_as_text(data):
    recipe = data.recipes.add_imported({
        "title": "Houmous", "servings": 4, "source_url": "https://example.com/houmous",
        "instructions": "1. Mixer.",
        "ingredients": [{"name": "pois chiches", "quantity": 400, "unit": "g"},
                        {"name": "zaatar", "quantity": 2, "unit": "tbsp"}]})
    assert [i["name"] for i in recipe["ingredients"]] == ["Pois chiches"]
    assert recipe["instructions"].endswith("Ingrédients non reconnus : zaatar")


def test_requests_for_new_products(data):
    request = data.products.request("Zaatar", data.user.id)
    assert data.products.requests()[0]["name"] == "Zaatar"
    assert data.products.close_request(request["id"]) and data.products.requests() == []
    with pytest.raises(ValueError, match="already exists"):
        data.products.request("tomates", data.user.id)


def test_database_v8_is_migrated_and_synced_without_loss(tmp_path):
    """A database like the real one: ingredients from before the file,
    plurals, a duplicate, and "pierre" which is no product."""
    db = tmp_path / "v8.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    for number in range(1, 9):
        [file] = MIGRATIONS_DIR.glob(f"{number:03d}_*.sql")
        conn.executescript(file.read_text())
    conn.executescript("""
        PRAGMA user_version = 8;
        INSERT INTO users (login, name) VALUES ('me@x.com', 'Grégory');
        INSERT INTO ingredients (name, aisle) VALUES
            ('pâtes (spaghetti)', 'autre'), ('spaghetti', 'autre'), ('pierre', 'autre'),
            ('tomate concassée', 'autre');
        INSERT INTO recipes (title, servings) VALUES ('Bolo', 4);
        INSERT INTO recipe_ingredients (recipe_id, position, ingredient_id, quantity, unit)
            VALUES (1, 0, 1, 400, 'g'), (1, 1, 3, 2, NULL), (1, 2, 4, 400, 'g');
        INSERT INTO shopping_items (ingredient_id, quantity, unit) VALUES (2, 500, 'g');
    """)
    conn.close()

    conn, owner = open_household(db, {"me@x.com": "Grégory"})
    data = user_data(conn, owner)
    recipe = data.recipes.get(1)
    assert [(i["name"], i["quantity"]) for i in recipe["ingredients"]] == [
        ("Pâtes", 400), ("pierre", 2), ("Tomates concassées", 400)]  # nothing lost
    assert data.shopping.list()[0]["name"] == "Pâtes"  # "spaghetti" merged into Pâtes
    assert data.shopping.list()[0]["aisle"] == "épicerie"  # aisle from the file
    retired = data.products.retired_in_use()
    assert retired == [{"name": "pierre", "recipes": "Bolo", "on_list": 0}]
    assert "pierre" not in data.products.names()  # not offered any more
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    open_household(db, {"me@x.com": "Grégory"})  # a second start changes nothing
    assert len(user_data(conn, owner).products.names()) == len(catalog().products)


def test_unknown_products_are_refused_before_asking(data):
    """Seen in real use: "poulet blanc" was refused AFTER the user said yes,
    so the model asked a second time with fixed names."""
    from assistant.agent.tools import ToolBox, ToolError
    asked = []
    box = ToolBox(data, confirm=lambda q: asked.append(q) or True)
    recipe = {"title": "Curry", "servings": 4, "instructions": "",
              "ingredients": [{"name": "poulet", "quantity": 500, "unit": "g"},
                              {"name": "zaatar", "quantity": 1, "unit": "tsp"}]}
    with pytest.raises(ToolError, match="zaatar"):
        box.run("save_recipe", recipe)
    assert asked == []  # the user was not asked for a save that cannot work


def test_suggestions_prefer_the_product_named_inside():
    """Seen in real use: "gousse de vanille" suggested Ail (alias "gousse d'ail")."""
    assert catalog().closest("gousse de vanille bourbon", "fr")[0] == "Vanille"
    assert catalog().find("jaunes d'œufs").key == "egg"
    assert catalog().find("crème liquide").key != catalog().find("crème fraîche").key


def test_tap_water_is_never_on_the_shopping_list(data):
    recipe = data.recipes.add("Pâte à choux", 4, [
        {"name": "eau", "quantity": 125, "unit": "ml"},
        {"name": "farine", "quantity": 150, "unit": "g"}])
    data.shopping.add_recipe(recipe["id"])
    assert [i["name"] for i in data.shopping.list()] == ["Farine"]
    with pytest.raises(ValueError, match="never bought"):
        data.shopping.add("eau du robinet")
    data.shopping.add("eau minérale", 6)  # bottled water: bought
