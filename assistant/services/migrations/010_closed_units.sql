-- Units are now a closed list: g, ml, tsp, tbsp, or NULL (pieces), so that
-- quantities of the same product add up (services/recipes.py, UNITS).
-- Rows written before keep their meaning:
-- - spoons written in words become tsp / tbsp;
-- - "2 cm" (of ginger...) is one piece;
-- - any other word (gousse, branche, tranche...) is a number of pieces.

UPDATE recipe_ingredients SET unit = 'tbsp' WHERE lower(unit) IN
    ('cuillère à soupe', 'cuillères à soupe', 'c. à s.', 'c.à.s', 'cas');
UPDATE recipe_ingredients SET unit = 'tsp' WHERE lower(unit) IN
    ('cuillère à café', 'cuillères à café', 'c. à c.', 'c.à.c', 'cac');
UPDATE recipe_ingredients SET quantity = 1, unit = NULL WHERE lower(unit) = 'cm';
UPDATE recipe_ingredients SET unit = NULL WHERE unit NOT IN ('g', 'ml', 'tsp', 'tbsp');

UPDATE shopping_items SET unit = 'tbsp' WHERE lower(unit) IN
    ('cuillère à soupe', 'cuillères à soupe', 'c. à s.', 'c.à.s', 'cas');
UPDATE shopping_items SET unit = 'tsp' WHERE lower(unit) IN
    ('cuillère à café', 'cuillères à café', 'c. à c.', 'c.à.c', 'cac');
UPDATE shopping_items SET quantity = 1, unit = NULL WHERE lower(unit) = 'cm';
UPDATE shopping_items SET unit = NULL WHERE unit NOT IN ('g', 'ml', 'tsp', 'tbsp');
