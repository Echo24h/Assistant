-- An ingredient catalog: recipes and the shopping list point to it
-- instead of each storing the name as text.

CREATE TABLE ingredients (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE,  -- lowercase, singular: "tomate"
    aisle TEXT NOT NULL DEFAULT 'autre' CHECK (aisle IN (
        'fruits et légumes', 'boulangerie', 'viande et poisson', 'frais', 'épicerie',
        'surgelés', 'boissons', 'maison', 'autre'))
);

-- Every name already used becomes an ingredient. (Plurals are merged at
-- start by services/ingredients.py, Ingredients.tidy: SQL cannot do it.)
INSERT OR IGNORE INTO ingredients (name) SELECT DISTINCT name FROM recipe_ingredients;
INSERT OR IGNORE INTO ingredients (name) SELECT DISTINCT name FROM shopping_items;

-- Rebuild both tables with ingredient_id instead of name (same copy-and-
-- rename as in 002; no other table points to these two).
CREATE TABLE recipe_ingredients_new (
    id            INTEGER PRIMARY KEY,
    recipe_id     INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
    quantity      REAL CHECK (quantity IS NULL OR quantity > 0),
    unit          TEXT
);
INSERT INTO recipe_ingredients_new (id, recipe_id, position, ingredient_id, quantity, unit)
    SELECT r.id, r.recipe_id, r.position, i.id, r.quantity, r.unit
    FROM recipe_ingredients r JOIN ingredients i ON i.name = r.name;
DROP TABLE recipe_ingredients;
ALTER TABLE recipe_ingredients_new RENAME TO recipe_ingredients;
CREATE INDEX recipe_ingredients_by_recipe ON recipe_ingredients (recipe_id, position);

CREATE TABLE shopping_items_new (
    id            INTEGER PRIMARY KEY,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
    quantity      REAL CHECK (quantity IS NULL OR quantity > 0),
    unit          TEXT,
    checked       INTEGER NOT NULL DEFAULT 0 CHECK (checked IN (0, 1)),
    recipe_id     INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    added_by      INTEGER REFERENCES users(id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO shopping_items_new (id, ingredient_id, quantity, unit, checked, recipe_id,
                                added_by, created_at)
    SELECT s.id, i.id, s.quantity, s.unit, s.checked, s.recipe_id, s.added_by, s.created_at
    FROM shopping_items s JOIN ingredients i ON i.name = s.name;
DROP TABLE shopping_items;
ALTER TABLE shopping_items_new RENAME TO shopping_items;
