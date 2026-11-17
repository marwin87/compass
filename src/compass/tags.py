"""Managing tags across all notes: rename (which merges when the new name exists) and delete.

Every operation runs in one transaction and re-indexes the notes it touched, because a note's tags
are part of its search index (and carry the highest weight in the ranking). Names are cleaned like
everywhere else (lowercase, spaces collapsed); a note keeps at most one row per tag, so notes that
already had both tags of a merge do not get a duplicate.
"""

import sqlite3

from compass.db import connect, index_note
from compass.notes import MAX_TAG_LEN, _clean


class TagError(Exception):
    def __init__(self, code: str, **info: object) -> None:
        super().__init__(code)
        self.code = code
        self.info = info


def _tag_id(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    return None if row is None else int(row[0])


def _reindex(conn: sqlite3.Connection, note_ids: list[int]) -> None:
    for note_id in note_ids:
        title, body = conn.execute(
            "SELECT title, body FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        names = [
            r[0]
            for r in conn.execute(
                "SELECT t.name FROM note_tags nt JOIN tags t ON t.id = nt.tag_id "
                "WHERE nt.note_id = ? ORDER BY t.name",
                (note_id,),
            )
        ]
        index_note(conn, note_id, title, body, names)


def _notes_with(conn: sqlite3.Connection, tag_id: int) -> list[int]:
    return [
        int(r[0])
        for r in conn.execute(
            "SELECT note_id FROM note_tags WHERE tag_id = ? ORDER BY note_id", (tag_id,)
        )
    ]


def rename(old: str, new: str) -> dict[str, object]:
    """Give a tag a new name on every note; an existing target name means a merge."""
    old_name, new_name = _clean(old), _clean(new)
    if not new_name or "," in new_name or len(new_name) > MAX_TAG_LEN:
        raise TagError("name_invalid", max=MAX_TAG_LEN)
    conn = connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            old_id = _tag_id(conn, old_name)
            if old_id is None:
                raise TagError("not_found")
            notes = _notes_with(conn, old_id)
            if new_name == old_name:
                return {
                    "name": old_name,
                    "count": len(notes),
                    "merged": False,
                    "notes": 0,
                }
            target = _tag_id(conn, new_name)
            if target is None:  # a plain rename
                conn.execute(
                    "UPDATE tags SET name = ? WHERE id = ?", (new_name, old_id)
                )
                final_id = old_id
            else:  # a merge: the target takes over the notes (those with both keep one row)
                conn.execute(
                    "INSERT OR IGNORE INTO note_tags(note_id, tag_id) "
                    "SELECT note_id, ? FROM note_tags WHERE tag_id = ?",
                    (target, old_id),
                )
                conn.execute("DELETE FROM note_tags WHERE tag_id = ?", (old_id,))
                conn.execute("DELETE FROM tags WHERE id = ?", (old_id,))
                final_id = target
            _reindex(conn, notes)
            count = len(_notes_with(conn, final_id))
    finally:
        conn.close()
    return {
        "name": new_name,
        "count": count,
        "merged": target is not None,
        "notes": len(notes),
    }


def delete(name: str) -> dict[str, object]:
    """Remove a tag from every note; the notes themselves stay."""
    clean = _clean(name)
    conn = connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            tag_id = _tag_id(conn, clean)
            if tag_id is None:
                raise TagError("not_found")
            notes = _notes_with(conn, tag_id)
            conn.execute("DELETE FROM note_tags WHERE tag_id = ?", (tag_id,))
            conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            _reindex(conn, notes)
    finally:
        conn.close()
    return {"name": clean, "notes": len(notes)}
