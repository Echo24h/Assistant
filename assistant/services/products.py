"""The product catalog: the only ingredients and shopping items accepted.

The list is written by the developer in assistant/data/products.toml
(versioned, reviewed, translatable). At start, the database follows it
(sync): recipes and the shopping list point to products by id, and each
product keeps its stable key from the file.

Strict: a name that matches no product is refused, with the closest
products as suggestions. A person can ask for a new product (requests);
the developer adds it to the file.

Matching ignores case, accents, typographic apostrophes and simple plurals
("Epinards", "tomates" -> the right product). It only FINDS a product; it
never changes the data. When in doubt, the name is not recognized.
"""

import difflib
import re
import sqlite3
import tomllib
import unicodedata
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

CATALOG_FILE = Path(__file__).resolve().parent.parent / "data" / "products.toml"

# In the order of a walk through the shop: the shopping list follows it.
AISLES = ("fruits et légumes", "boulangerie", "viande et poisson", "frais", "épicerie",
          "surgelés", "boissons", "maison", "autre")
# ASSISTANT_LANGUAGE -> the name used in the file. Default: English.
LANGUAGE_CODES = {"french": "fr", "français": "fr", "english": "en"}

# Words ending in s that are not plurals (written without accents: see normalize).
INVARIABLE = {"ananas", "anchois", "brebis", "cassis", "frais", "gras", "jus", "mais",
              "pois", "radis", "pates", "epinards", "lardons", "chips", "noix", "riz", "os"}


def aisle_order(column: str = "aisle") -> str:
    """SQL to sort by aisle in the shop's order. `column` is always ours, never user input."""
    cases = " ".join(f"WHEN '{aisle}' THEN {n}" for n, aisle in enumerate(AISLES))
    return f"CASE {column} {cases} END"


def singular(word: str) -> str:
    """"tomates" -> "tomate", "poireaux" -> "poireau". Careful: when in doubt, unchanged."""
    if len(word) <= 3 or word in INVARIABLE or not word.isalpha():
        return word
    if word.endswith(("eaux", "oux")):
        return word[:-1]
    if word.endswith("s") and word[-2] in "bcdefghklmnprtvz":
        return word[:-1]
    return word


def normalize(text: str) -> str:
    """"  Épinards  " -> "epinards", "Œufs" -> "oeuf": the form used to compare names."""
    text = text.replace("œ", "oe").replace("Œ", "Oe").replace("’", "'")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))  # drop accents
    words = re.sub(r"\s+", " ", text.casefold().strip()).split(" ")
    return " ".join(singular(word) for word in words)


@dataclass(frozen=True)
class Product:
    key: str
    names: dict[str, str]  # language code -> name
    aisle: str
    aliases: tuple[str, ...] = field(default=())
    shop: bool = True  # False: used in recipes, never bought (tap water)

    def name(self, language: str) -> str:
        return self.names.get(language) or self.names.get("en") or self.key


class Catalog:
    """The products of the file, and how to find one from what someone wrote."""

    def __init__(self, products: list[Product]):
        self.products = {p.key: p for p in products}
        self.index: dict[str, str] = {}  # normalized name (any language), alias or key -> key
        for product in products:
            for written in [*product.names.values(), *product.aliases, product.key]:
                found = self.index.setdefault(normalize(written), product.key)
                if found != product.key:  # a mistake in the file: refuse to start
                    raise ValueError(f"products.toml: «{written}» is both {found} and "
                                     f"{product.key}")

    def find(self, written: str) -> Product | None:
        key = self.index.get(normalize(written))
        return self.products[key] if key else None

    def closest(self, written: str, language: str, n: int = 3) -> list[str]:
        """Names of the products that look the most like `written` (for an error).

        First the products whose name is a whole word of it ("gousse de
        vanille" -> Vanille), then names that are spelled alike ("tomat" ->
        Tomate). Compared with the names in this language and the aliases
        only: not with the English keys or other languages ("tomat" is not "oats").
        """
        text = normalize(written)
        inside = [p.name(language) for p in self.products.values()
                  if re.search(rf"\b{re.escape(normalize(p.name(language)))}\b", text)]
        inside.sort(key=len, reverse=True)  # "huile d'olive" before "huile"
        candidates = {}  # normalized -> product key
        for product in self.products.values():
            for written_form in [product.name(language), *product.aliases]:
                candidates.setdefault(normalize(written_form), product.key)
        found = difflib.get_close_matches(text, candidates, n=n * 2, cutoff=0.75)
        alike = [self.products[candidates[f]].name(language) for f in found]
        return list(dict.fromkeys(inside + alike))[:n]


def read_catalog(path: Path = CATALOG_FILE) -> Catalog:
    """Read and check the file. Any mistake stops the app at start, not later."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    products = []
    for key, entry in data.items():
        if not re.fullmatch(r"[a-z0-9_]+", key):
            raise ValueError(f"products.toml: key «{key}»: a-z, 0-9 and _ only")
        names = {lang: name for lang, name in entry.items()
                 if lang not in ("aisle", "aliases", "shop")}
        if not names or not all(isinstance(n, str) and n.strip() for n in names.values()):
            raise ValueError(f"products.toml: [{key}] needs names, e.g. fr = \"...\"")
        if entry.get("aisle") not in AISLES:
            raise ValueError(f"products.toml: [{key}] aisle must be one of {AISLES}")
        if not isinstance(entry.get("shop", True), bool):
            raise ValueError(f"products.toml: [{key}] shop must be true or false")
        products.append(Product(key, names, entry["aisle"], tuple(entry.get("aliases", ())),
                                entry.get("shop", True)))
    return Catalog(products)


@cache
def catalog() -> Catalog:
    """The catalog of the file, read once per run."""
    return read_catalog()


def language_code(language: str) -> str:
    return LANGUAGE_CODES.get(language.strip().lower(), "en")


class Products:
    """The products in the database (ids for recipes and the shopping list)."""

    def __init__(self, conn: sqlite3.Connection, catalog: Catalog, language: str = "fr"):
        self.conn = conn
        self.catalog = catalog
        self.language = language

    def id_for(self, written: str) -> int:
        """The id of the product this name means. Strict: ValueError if none,
        with suggestions. Runs inside the caller's transaction."""
        product = self.catalog.find(written)
        if product is None:
            close = self.catalog.closest(written, self.language)
            hint = f" Close: {', '.join(close)}." if close else ""
            raise ValueError(f'Unknown product "{written.strip()}".{hint} '
                             "New products are added by the developer (ask for it).")
        row = self.conn.execute("SELECT id FROM products WHERE key = ?", (product.key,)).fetchone()
        if row is None:
            raise ValueError(f'"{written}" is not synced yet: restart the app.')
        return row["id"]

    def check_known(self, names: list[str]) -> None:
        """Refuse a list if ANY name is unknown, naming them all at once (one
        error for the whole recipe, not one round trip per ingredient)."""
        problems = []
        for name in names:
            if self.catalog.find(name) is None:
                close = self.catalog.closest(name, self.language)
                problems.append(f'"{name.strip()}"' + (f" (close: {', '.join(close)})" if close else ""))
        if problems:
            raise ValueError("Unknown products: " + "; ".join(problems) + ". Use the close "
                             "names, or ask the developer to add a product.")

    def names(self) -> list[str]:
        """Names of the products that can be chosen, for suggestions in the page."""
        rows = self.conn.execute(
            "SELECT name FROM products WHERE retired = 0 ORDER BY name COLLATE NOCASE")
        return [row["name"] for row in rows]

    def sync(self) -> None:
        """Make the database follow the file (run at start, in one transaction).

        - a row with a known key: name (in the language) and aisle updated;
        - an old row without key (from before the file) that matches a
          product: it becomes that product; two matching the same product
          are merged (everything that pointed to one points to the other);
        - a product new in the file: added;
        - a row whose product is gone, or that matches nothing: retired
          (kept, because recipes may use it; not offered any more).
        """
        with self.conn:
            for row in self.conn.execute(
                    "SELECT id, name FROM products WHERE key IS NULL").fetchall():
                product = self.catalog.find(row["name"])
                if product is None:
                    continue
                same = self.conn.execute("SELECT id FROM products WHERE key = ?",
                                         (product.key,)).fetchone()
                if same is None:
                    self.conn.execute("UPDATE products SET key = ? WHERE id = ?",
                                      (product.key, row["id"]))
                else:
                    self._merge(row["id"], into=same["id"])

            for product in self.catalog.products.values():
                name = product.name(self.language)
                # Names are unique: if another (retired) row has this name, rename it.
                self.conn.execute(
                    "UPDATE products SET name = name || ' (retired #' || id || ')' "
                    "WHERE name = ? AND (key IS NULL OR key != ?)", (name, product.key))
                updated = self.conn.execute(
                    "UPDATE products SET name = ?, aisle = ?, retired = 0 WHERE key = ?",
                    (name, product.aisle, product.key))
                if updated.rowcount == 0:
                    self.conn.execute("INSERT INTO products (key, name, aisle) VALUES (?, ?, ?)",
                                      (product.key, name, product.aisle))

            keys = list(self.catalog.products)
            self.conn.execute(
                f"UPDATE products SET retired = 1 WHERE key IS NULL "
                f"OR key NOT IN ({', '.join('?' * len(keys))})", keys)

    def _merge(self, old: int, into: int) -> None:
        for table in ("recipe_ingredients", "shopping_items"):
            self.conn.execute(f"UPDATE {table} SET product_id = ? WHERE product_id = ?",
                              (into, old))
        self.conn.execute("DELETE FROM products WHERE id = ?", (old,))

    def retired_in_use(self) -> list[dict]:
        """Products not (or no longer) in the file, but still used: to fix."""
        rows = self.conn.execute(
            "SELECT p.name, "
            " (SELECT group_concat(DISTINCT r.title) FROM recipe_ingredients ri "
            "  JOIN recipes r ON r.id = ri.recipe_id WHERE ri.product_id = p.id) AS recipes, "
            " (SELECT COUNT(*) FROM shopping_items s WHERE s.product_id = p.id) AS on_list "
            "FROM products p WHERE p.retired = 1 ORDER BY p.name")
        return [dict(row) for row in rows if row["recipes"] or row["on_list"]]

    # --- asking the developer for a product ---

    def request(self, name: str, user_id: int) -> dict:
        name = name.strip()
        if not 0 < len(name) <= 100:
            raise ValueError("name: 1 to 100 characters")
        if self.catalog.find(name):
            raise ValueError(f'"{name}" already exists: {self.catalog.find(name).name(self.language)}.')
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO product_requests (name, requested_by) VALUES (?, ?)",
                (name, user_id))
        return {"id": cur.lastrowid, "status": "open"}

    def requests(self, status: str = "open") -> list[dict]:
        rows = self.conn.execute(
            "SELECT q.id, q.name, u.name AS requested_by, "
            "datetime(q.created_at, 'localtime') AS created_at "
            "FROM product_requests q LEFT JOIN users u ON u.id = q.requested_by "
            "WHERE q.status = ? ORDER BY q.id", (status,))
        return [dict(row) for row in rows]

    def close_request(self, request_id: int) -> bool:
        with self.conn:
            cur = self.conn.execute("UPDATE product_requests SET status = 'done' WHERE id = ?",
                                    (request_id,))
        return cur.rowcount == 1
