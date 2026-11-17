import re
from datetime import UTC, datetime

from pydantic import BaseModel

from compass.db import connect

LIMIT = 50
COLUMNS = "n.id, n.title, n.body, n.created_at"


class Note(BaseModel):
    id: int
    title: str
    body: str
    created_at: str


def match_query(q: str) -> str:
    """Turn user input into a safe FTS5 query: any word, as a prefix.

    Only word characters survive, so quotes and FTS operators in the input
    cannot break the query. Empty result means "no filter".
    """
    return " OR ".join(f'"{word}"*' for word in re.findall(r"\w+", q))


def create_note(title: str, body: str) -> Note:
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO notes(title, body, created_at) VALUES (?, ?, ?)",
                (title, body, created_at),
            )
            note_id = cur.lastrowid
            assert note_id is not None
            conn.execute(
                "INSERT INTO notes_fts(rowid, title, body) VALUES (?, ?, ?)",
                (note_id, title, body),
            )
    finally:
        conn.close()
    return Note(id=note_id, title=title, body=body, created_at=created_at)


def get_note(note_id: int) -> Note | None:
    conn = connect()
    try:
        row = conn.execute(
            f"SELECT {COLUMNS} FROM notes n WHERE n.id = ?", (note_id,)
        ).fetchone()
    finally:
        conn.close()
    return (
        Note(id=row[0], title=row[1], body=row[2], created_at=row[3]) if row else None
    )


def list_notes(q: str = "") -> list[Note]:
    match = match_query(q)
    conn = connect()
    try:
        if match:
            rows = conn.execute(
                f"SELECT {COLUMNS} FROM notes n WHERE n.id IN "
                "(SELECT rowid FROM notes_fts WHERE notes_fts MATCH ?) "
                "ORDER BY n.id DESC LIMIT ?",
                (match, LIMIT),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {COLUMNS} FROM notes n ORDER BY n.id DESC LIMIT ?", (LIMIT,)
            ).fetchall()
    finally:
        conn.close()
    return [Note(id=r[0], title=r[1], body=r[2], created_at=r[3]) for r in rows]
