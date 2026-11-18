"""The AI summary of a note, kept next to it (one per note, table `note_summaries`).

A summary is not part of the note: it is not searched, and it goes away with the note. It remembers
a digest of the title and text it was written from, so it can say it is *stale* once the note has
been edited (it is still shown, with a warning).
"""

import hashlib
import sqlite3
from datetime import UTC, datetime

from pydantic import BaseModel

from compass.db import connect

MAX_SUMMARY = 20000


class Summary(BaseModel):
    text: str
    created_at: str
    stale: bool  # the note changed after this summary was written


def digest(title: str, body: str) -> str:
    return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def insert(
    conn: sqlite3.Connection,
    note_id: int,
    text: str,
    created_at: str,
    source_hash: str,
) -> None:
    """Write the summary of a note inside the caller's transaction (a second one replaces the first)."""
    conn.execute(
        "INSERT OR REPLACE INTO note_summaries(note_id, text, created_at, source_hash) "
        "VALUES (?, ?, ?, ?)",
        (note_id, text, created_at, source_hash),
    )


def save(note_id: int, text: str, source_hash: str) -> Summary | None:
    """Keep a summary written from the note as `source_hash` describes it (the digest taken when the
    model was asked, so an edit made while it worked marks the summary stale). None: no such note."""
    created_at = now()
    conn = connect()
    try:
        with conn:
            insert(conn, note_id, text, created_at, source_hash)
    except sqlite3.IntegrityError:  # the note was deleted meanwhile
        return None
    finally:
        conn.close()
    return get(note_id)


_SELECT = (
    "SELECT s.note_id, s.text, s.created_at, s.source_hash, n.title, n.body "
    "FROM note_summaries s JOIN notes n ON n.id = s.note_id"
)


def _make(row: tuple[int, str, str, str, str, str]) -> Summary:
    return Summary(
        text=row[1], created_at=row[2], stale=row[3] != digest(row[4], row[5])
    )


def get(note_id: int) -> Summary | None:
    conn = connect()
    try:
        row = conn.execute(_SELECT + " WHERE s.note_id = ?", (note_id,)).fetchone()
    finally:
        conn.close()
    return None if row is None else _make(row)


def all_by_note() -> dict[int, Summary]:
    """Every summary by note id (for the export file)."""
    conn = connect()
    try:
        rows = conn.execute(_SELECT).fetchall()
    finally:
        conn.close()
    return {r[0]: _make(r) for r in rows}


def delete(note_id: int) -> None:
    conn = connect()
    try:
        with conn:
            conn.execute("DELETE FROM note_summaries WHERE note_id = ?", (note_id,))
    finally:
        conn.close()
