-- Shared expenses of the household: who paid, and each person's share.

CREATE TABLE expenses (
    id           INTEGER PRIMARY KEY,
    day          TEXT NOT NULL,  -- YYYY-MM-DD
    description  TEXT NOT NULL,
    category     TEXT NOT NULL,
    -- Money in CENTS, as an integer: floats cannot hold 0.10 exactly.
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    paid_by      INTEGER NOT NULL REFERENCES users(id),
    created_by   INTEGER REFERENCES users(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX expenses_by_day ON expenses (day);

-- Who owes what for each expense. The shares of an expense add up to its
-- amount (checked in services/finances.py). Works for any number of people.
CREATE TABLE expense_shares (
    expense_id   INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    PRIMARY KEY (expense_id, user_id)
);
