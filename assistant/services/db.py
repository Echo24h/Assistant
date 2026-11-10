"""SQLite connection and schema migrations.

The schema is a list of numbered SQL files in migrations/ (001_..., 002_...).
SQLite stores a number in the database file (PRAGMA user_version): at
start, every file with a higher number is applied, in order, each in one
transaction (all of the file or nothing), then the number is updated.
To change the schema: add a new file, never edit an applied one.
"""

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(path: Path | str) -> sqlite3.Connection:
    """Open the database, ready to use and up to date."""
    # check_same_thread=False: the web server uses a connection from several
    # threads, always behind a lock (web/api.py).
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")  # off by default in SQLite
    conn.execute("PRAGMA busy_timeout = 5000")  # wait up to 5 s if another connection writes
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")  # readers do not block the writer
    migrate(conn)
    return conn


def migrations() -> list[tuple[int, Path]]:
    """[(1, .../001_tasks_workouts.sql), (2, ...), ...] sorted by number."""
    files = [(int(f.name.split("_")[0]), f) for f in MIGRATIONS_DIR.glob("*.sql")]
    return sorted(files)


def migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for number, file in migrations():
        if number <= version:
            continue  # already applied
        script = f"BEGIN;\n{file.read_text()}\nPRAGMA user_version = {number};\nCOMMIT;"
        try:
            conn.executescript(script)
        except sqlite3.Error:
            conn.rollback()  # the database stays at the previous version
            raise
