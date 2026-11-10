-- The ingredient catalog becomes the product catalog, written by the
-- developer in assistant/data/products.toml (services/products.py syncs it).

-- "Papier toilette" is not an ingredient: the table and columns are renamed.
-- SQLite also updates the foreign keys that point to the renamed table.
ALTER TABLE ingredients RENAME TO products;
ALTER TABLE recipe_ingredients RENAME COLUMN ingredient_id TO product_id;
ALTER TABLE shopping_items RENAME COLUMN ingredient_id TO product_id;

-- The stable key from the file ("tomato"). NULL: a row from before the file,
-- matched to a product (or retired) by the sync at start.
ALTER TABLE products ADD COLUMN key TEXT;
CREATE UNIQUE INDEX products_by_key ON products (key);
-- 1: no longer in the file (or never matched): kept for the recipes that
-- use it, but not offered any more.
ALTER TABLE products ADD COLUMN retired INTEGER NOT NULL DEFAULT 0 CHECK (retired IN (0, 1));

-- "Please add this product": asked in the page or the chat, read by the
-- developer (python -m assistant products).
CREATE TABLE product_requests (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    requested_by INTEGER REFERENCES users(id),
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
