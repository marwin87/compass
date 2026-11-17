import os
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from compass.search import fold

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS notes(
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tags(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS note_tags(
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag_id)
);
CREATE INDEX IF NOT EXISTS note_tags_tag ON note_tags(tag_id);
"""

# The search index holds *folded* text (see search.fold), one row per note, rowid = note id.
# It is created (and old databases migrated) by _ensure_index, not by SCHEMA.
FTS_VERSION = "2"


def db_path() -> Path:
    return Path(os.environ.get("COMPASS_DB_PATH", "data/compass.db"))


def index_note(
    conn: sqlite3.Connection, note_id: int, title: str, body: str, tags: Sequence[str]
) -> None:
    """(Re)write a note's row in the search index."""
    conn.execute("DELETE FROM notes_fts WHERE rowid = ?", (note_id,))
    conn.execute(
        "INSERT INTO notes_fts(rowid, title, body, tags) VALUES (?, ?, ?, ?)",
        (note_id, fold(title), fold(body), fold(" ".join(tags))),
    )


def unindex_note(conn: sqlite3.Connection, note_id: int) -> None:
    conn.execute("DELETE FROM notes_fts WHERE rowid = ?", (note_id,))


def _index_version(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = 'fts_version'").fetchone()
    return None if row is None else str(row[0])


def _ensure_index(conn: sqlite3.Connection) -> None:
    """Create the folded index, rebuilding it once for databases made by older versions."""
    if _index_version(conn) == FTS_VERSION:
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        if (
            _index_version(conn) != FTS_VERSION
        ):  # re-check: another connection may have won
            conn.execute("DROP TABLE IF EXISTS notes_vocab")
            conn.execute("DROP TABLE IF EXISTS notes_fts")
            conn.execute("CREATE VIRTUAL TABLE notes_fts USING fts5(title, body, tags)")
            conn.execute(
                "CREATE VIRTUAL TABLE notes_vocab USING fts5vocab(notes_fts, 'row')"
            )
            rows = conn.execute(
                "SELECT n.id, n.title, n.body, (SELECT group_concat(t.name, char(10)) "
                "FROM note_tags nt JOIN tags t ON t.id = nt.tag_id WHERE nt.note_id = n.id) "
                "FROM notes n"
            ).fetchall()
            for note_id, title, body, tags in rows:
                index_note(conn, note_id, title, body, tags.split("\n") if tags else [])
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('fts_version', ?)",
                (FTS_VERSION,),
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")  # off by default; cascades need it
    conn.executescript(SCHEMA)
    _ensure_index(conn)
    return conn
