-- The schema before migrations existed. IF NOT EXISTS: on a database created
-- by that older version, this file changes nothing.

CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    due_date   TEXT,
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    priority   TEXT NOT NULL DEFAULT 'normal'
);

CREATE TABLE IF NOT EXISTS workouts (
    id           INTEGER PRIMARY KEY,
    day          TEXT NOT NULL,
    activity     TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    notes        TEXT
);
