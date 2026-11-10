-- Bugs reported by the household (button in the page, or the chat).
-- Local only: nothing is sent to GitHub or anywhere else.

CREATE TABLE bug_reports (
    id          INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    place       TEXT NOT NULL,  -- where: "chat", "tasks"... or "agent"
    details     TEXT,           -- context: last error, recent messages, browser
    version     TEXT,           -- git commit of the code that had the bug
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'fixed')),
    reported_by INTEGER REFERENCES users(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
