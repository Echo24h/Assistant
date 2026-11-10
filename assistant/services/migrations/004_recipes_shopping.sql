-- Recipes and the shopping list, both shared by the household.

CREATE TABLE recipes (
    id           INTEGER PRIMARY KEY,
    title        TEXT NOT NULL,
    servings     INTEGER NOT NULL CHECK (servings > 0),  -- number of people
    instructions TEXT NOT NULL DEFAULT '',
    source_url   TEXT,  -- when imported from a website
    created_by   INTEGER REFERENCES users(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE recipe_ingredients (
    id        INTEGER PRIMARY KEY,
    -- CASCADE: deleting a recipe deletes its ingredients.
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,  -- order in the recipe
    name      TEXT NOT NULL,     -- lowercase, e.g. "tomato"
    quantity  REAL CHECK (quantity IS NULL OR quantity > 0),  -- NULL: "some" (salt)
    unit      TEXT               -- g, ml, tsp, tbsp... NULL: pieces
);
CREATE INDEX recipe_ingredients_by_recipe ON recipe_ingredients (recipe_id, position);

CREATE TABLE shopping_items (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    quantity   REAL CHECK (quantity IS NULL OR quantity > 0),
    unit       TEXT,
    checked    INTEGER NOT NULL DEFAULT 0 CHECK (checked IN (0, 1)),  -- in the cart
    -- SET NULL: deleting a recipe keeps the items already on the list.
    recipe_id  INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    added_by   INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
