import re
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from compass.db import connect

LIMIT = 50
MAX_TAGS = 10
MAX_TAG_LEN = 30
COLUMNS = "n.id, n.title, n.body, n.created_at"


class Note(BaseModel):
    id: int
    title: str
    body: str
    created_at: str
    tags: list[str] = []


class TagCount(BaseModel):
    name: str
    count: int


def _clean(tag: str) -> str:
    return " ".join(tag.lower().split())


def normalize_tags(raw: Iterable[str]) -> list[str]:
    """Lowercase, trim, collapse spaces, drop empties and duplicates; sorted."""
    tags: set[str] = set()
    for item in raw:
        tag = _clean(item)
        if not tag:
            continue
        if "," in tag or len(tag) > MAX_TAG_LEN:
            raise ValueError(f"a tag must be 1-{MAX_TAG_LEN} characters, no commas")
        tags.add(tag)
    if len(tags) > MAX_TAGS:
        raise ValueError(f"at most {MAX_TAGS} tags per note")
    return sorted(tags)


def match_query(q: str) -> str:
    """Turn user input into a safe FTS5 query: any word, as a prefix.

    Only word characters survive, so quotes and FTS operators in the input
    cannot break the query. Empty result means "no filter".
    """
    return " OR ".join(f'"{word}"*' for word in re.findall(r"\w+", q))


def _save_tags(conn: sqlite3.Connection, note_id: int, tags: Sequence[str]) -> None:
    conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
    for tag in tags:
        conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (tag,))
        conn.execute(
            "INSERT INTO note_tags(note_id, tag_id) "
            "SELECT ?, id FROM tags WHERE name = ?",
            (note_id, tag),
        )


def _drop_unused_tags(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM note_tags)")


def _with_tags(conn: sqlite3.Connection, rows: Sequence[Sequence[Any]]) -> list[Note]:
    ids = [r[0] for r in rows]
    by_note: dict[int, list[str]] = {i: [] for i in ids}
    if ids:
        marks = ",".join("?" * len(ids))
        for note_id, name in conn.execute(
            "SELECT nt.note_id, t.name FROM note_tags nt "
            f"JOIN tags t ON t.id = nt.tag_id WHERE nt.note_id IN ({marks}) "
            "ORDER BY t.name",
            ids,
        ):
            by_note[note_id].append(name)
    return [
        Note(
            id=r[0],
            title=r[1],
            body=r[2],
            created_at=r[3],
            tags=by_note[r[0]],
        )
        for r in rows
    ]


def create_note(title: str, body: str, tags: Sequence[str] = ()) -> Note:
    clean = normalize_tags(tags)
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
            _save_tags(conn, note_id, clean)
    finally:
        conn.close()
    return Note(id=note_id, title=title, body=body, created_at=created_at, tags=clean)


def get_note(note_id: int) -> Note | None:
    conn = connect()
    try:
        rows = conn.execute(
            f"SELECT {COLUMNS} FROM notes n WHERE n.id = ?", (note_id,)
        ).fetchall()
        found = _with_tags(conn, rows)
    finally:
        conn.close()
    return found[0] if found else None


def list_notes(q: str = "", tags: Iterable[str] = ()) -> list[Note]:
    conditions: list[str] = []
    params: list[object] = []
    match = match_query(q)
    if match:
        conditions.append(
            "n.id IN (SELECT rowid FROM notes_fts WHERE notes_fts MATCH ?)"
        )
        params.append(match)
    wanted = sorted({c for c in (_clean(t) for t in tags) if c})
    if wanted:
        marks = ",".join("?" * len(wanted))
        conditions.append(
            "n.id IN (SELECT nt.note_id FROM note_tags nt "
            "JOIN tags t ON t.id = nt.tag_id "
            f"WHERE t.name IN ({marks}) "
            "GROUP BY nt.note_id HAVING COUNT(DISTINCT t.name) = ?)"
        )
        params.extend(wanted)
        params.append(len(wanted))
    where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
    conn = connect()
    try:
        rows = conn.execute(
            f"SELECT {COLUMNS} FROM notes n {where}ORDER BY n.id DESC LIMIT ?",
            (*params, LIMIT),
        ).fetchall()
        return _with_tags(conn, rows)
    finally:
        conn.close()


def list_tags() -> list[TagCount]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT t.name, COUNT(*) AS c FROM note_tags nt "
            "JOIN tags t ON t.id = nt.tag_id GROUP BY t.id ORDER BY c DESC, t.name"
        ).fetchall()
    finally:
        conn.close()
    return [TagCount(name=r[0], count=r[1]) for r in rows]


def update_note(
    note_id: int, title: str, body: str, tags: Sequence[str] = ()
) -> Note | None:
    """Replace title, body and tags, keeping the FTS index in step.

    The external-content index only forgets old words when told the OLD values
    via the 'delete' command, so the old row is read inside the same transaction.
    """
    clean = normalize_tags(tags)
    conn = connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT title, body, created_at FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE notes SET title = ?, body = ? WHERE id = ?",
                (title, body, note_id),
            )
            conn.execute(
                "INSERT INTO notes_fts(notes_fts, rowid, title, body) "
                "VALUES ('delete', ?, ?, ?)",
                (note_id, row[0], row[1]),
            )
            conn.execute(
                "INSERT INTO notes_fts(rowid, title, body) VALUES (?, ?, ?)",
                (note_id, title, body),
            )
            _save_tags(conn, note_id, clean)
            _drop_unused_tags(conn)
    finally:
        conn.close()
    return Note(id=note_id, title=title, body=body, created_at=row[2], tags=clean)


def delete_note(note_id: int) -> bool:
    """Remove a note, its index entry and tags nobody uses any more."""
    conn = connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT title, body FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                "INSERT INTO notes_fts(notes_fts, rowid, title, body) "
                "VALUES ('delete', ?, ?, ?)",
                (note_id, row[0], row[1]),
            )
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))  # cascades
            _drop_unused_tags(conn)
    finally:
        conn.close()
    return True
