-- The people of the household, and who owns what.

CREATE TABLE users (
    id    INTEGER PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,  -- Tailscale login, lowercase
    name  TEXT NOT NULL
);

-- SQLite cannot add a foreign key or a CHECK to an existing table. The
-- usual way: create the new table, copy the rows, drop the old one, rename.

CREATE TABLE tasks_new (
    id         INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    due_date   TEXT,  -- YYYY-MM-DD, or NULL
    priority   TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('high', 'normal', 'low')),
    done       INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1)),
    owner_id   INTEGER REFERENCES users(id),  -- NULL = shared by the household
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO tasks_new (id, title, due_date, priority, done, created_at)
    SELECT id, title, due_date, priority, done, created_at FROM tasks;
DROP TABLE tasks;
ALTER TABLE tasks_new RENAME TO tasks;

CREATE TABLE workouts_new (
    id           INTEGER PRIMARY KEY,
    -- Always personal. NULL only for rows older than this file: they are
    -- given to the owner when the app starts (users.sync_users).
    user_id      INTEGER REFERENCES users(id),
    day          TEXT NOT NULL,  -- YYYY-MM-DD
    activity     TEXT NOT NULL,  -- e.g. run, strength, swim
    duration_min INTEGER NOT NULL CHECK (duration_min > 0),
    notes        TEXT
);
INSERT INTO workouts_new (id, day, activity, duration_min, notes)
    SELECT id, day, activity, duration_min, notes FROM workouts;
DROP TABLE workouts;
ALTER TABLE workouts_new RENAME TO workouts;

CREATE INDEX workouts_by_user_day ON workouts (user_id, day);
