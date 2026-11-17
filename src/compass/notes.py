import sqlite3
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from compass.db import connect, index_note, unindex_note
from compass.search import fuzzy_terms, rank_key, words

LIMIT = 50
CANDIDATES = 200  # notes fetched from the index (best bm25 first) before re-ranking
BM25_WEIGHTS = "10.0, 1.0, 20.0"  # title, body, tags
MAX_TITLE = 200
MAX_BODY = 20000
MAX_TAGS = 10
MAX_TAG_LEN = 30
COLUMNS = "n.id, n.title, n.body, n.created_at"


class Note(BaseModel):
    id: int
    title: str
    body: str
    created_at: str
    tags: list[str] = []


@dataclass(frozen=True)
class ParsedNote:
    """A note read from an export file, already validated (see `transfer.parse_export`)."""

    title: str
    body: str
    tags: tuple[str, ...]
    created_at: str  # kept exactly as written in the file
    when: datetime  # the same moment, timezone-aware, used only for ordering


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


def match_query(tokens: Sequence[str], fuzzy: dict[str, set[str]]) -> str:
    """Safe FTS5 query: every word as a prefix, plus its typo variants as exact terms.

    Tokens are folded `[^\\W_]+` words, so quotes and FTS operators in the user's input
    cannot reach the query.
    """
    parts = [f'"{t}"*' for t in tokens]
    parts += [f'"{f}"' for t in tokens for f in sorted(fuzzy.get(t, ()))]
    return " OR ".join(dict.fromkeys(parts))


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
            _save_tags(conn, note_id, clean)
            index_note(conn, note_id, title, body, clean)
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


def _tag_filter(tags: Iterable[str]) -> tuple[str, list[object]] | None:
    wanted = sorted({c for c in (_clean(t) for t in tags) if c})
    if not wanted:
        return None
    marks = ",".join("?" * len(wanted))
    sql = (
        "SELECT nt.note_id FROM note_tags nt JOIN tags t ON t.id = nt.tag_id "
        f"WHERE t.name IN ({marks}) "
        "GROUP BY nt.note_id HAVING COUNT(DISTINCT t.name) = ?"
    )
    return sql, [*wanted, len(wanted)]


def list_notes(q: str = "", tags: Iterable[str] = ()) -> list[Note]:
    """Newest first without a query; otherwise the most relevant notes first."""
    tokens = words(q)
    tag_filter = _tag_filter(tags)
    conn = connect()
    try:
        if not tokens:
            where, params = "", []
            if tag_filter:
                where, params = f"WHERE n.id IN ({tag_filter[0]}) ", tag_filter[1]
            rows = conn.execute(
                f"SELECT {COLUMNS} FROM notes n {where}ORDER BY n.id DESC LIMIT ?",
                (*params, LIMIT),
            ).fetchall()
            return _with_tags(conn, rows)

        vocab = [r[0] for r in conn.execute("SELECT term FROM notes_vocab")]
        fuzzy = {t: fuzzy_terms(t, vocab) for t in set(tokens)}
        sql = "SELECT rowid FROM notes_fts WHERE notes_fts MATCH ?"
        params = [match_query(tokens, fuzzy)]
        if tag_filter:
            sql += f" AND rowid IN ({tag_filter[0]})"
            params += tag_filter[1]
        sql += f" ORDER BY bm25(notes_fts, {BM25_WEIGHTS}) LIMIT ?"
        ids = [r[0] for r in conn.execute(sql, (*params, CANDIDATES))]
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT {COLUMNS} FROM notes n WHERE n.id IN ({marks})", ids
        ).fetchall()
        candidates = _with_tags(conn, rows)
    finally:
        conn.close()
    candidates.sort(
        key=lambda n: (*rank_key(tokens, n.title, n.body, n.tags, fuzzy), n.id),
        reverse=True,
    )
    return candidates[:LIMIT]


def export_all() -> list[Note]:
    """Every note with its tags, newest first, in one consistent query (no limit, no ranking)."""
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT n.id, n.title, n.body, n.created_at, group_concat(t.name, char(10)) "
            "FROM notes n "
            "LEFT JOIN note_tags nt ON nt.note_id = n.id "
            "LEFT JOIN tags t ON t.id = nt.tag_id "
            "GROUP BY n.id ORDER BY n.id DESC"
        ).fetchall()
    finally:
        conn.close()
    return [
        Note(
            id=r[0],
            title=r[1],
            body=r[2],
            created_at=r[3],
            tags=sorted(r[4].split("\n")) if r[4] else [],
        )
        for r in rows
    ]


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
    """Replace title, body and tags, keeping the search index in step."""
    clean = normalize_tags(tags)
    conn = connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT created_at FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE notes SET title = ?, body = ? WHERE id = ?",
                (title, body, note_id),
            )
            _save_tags(conn, note_id, clean)
            _drop_unused_tags(conn)
            index_note(conn, note_id, title, body, clean)
    finally:
        conn.close()
    return Note(id=note_id, title=title, body=body, created_at=row[0], tags=clean)


def delete_note(note_id: int) -> bool:
    """Remove a note, its index entry and tags nobody uses any more."""
    conn = connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT id FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
            if row is None:
                return False
            unindex_note(conn, note_id)
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))  # cascades
            _drop_unused_tags(conn)
    finally:
        conn.close()
    return True


def import_notes(items: Sequence[ParsedNote]) -> tuple[int, int]:
    """Write validated notes in one transaction; returns (imported, skipped).

    A note whose (title, body, created_at) already exists is skipped, counted as a multiset: a
    file with two identical notes next to one existing copy imports exactly one. Notes go in
    oldest first (an export is newest first) so the new ids follow creation order.
    """
    # The file is newest first, so among equal times the later file position is the older note.
    ordered = [p for _, p in sorted(enumerate(items), key=lambda e: (e[1].when, -e[0]))]
    conn = connect()
    imported = skipped = 0
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = Counter(
                conn.execute("SELECT title, body, created_at FROM notes")
            )
            for p in ordered:
                key = (p.title, p.body, p.created_at)
                if existing[key] > 0:
                    existing[key] -= 1
                    skipped += 1
                    continue
                cur = conn.execute(
                    "INSERT INTO notes(title, body, created_at) VALUES (?, ?, ?)", key
                )
                note_id = cur.lastrowid
                assert note_id is not None
                _save_tags(conn, note_id, p.tags)
                index_note(conn, note_id, p.title, p.body, p.tags)
                imported += 1
    finally:
        conn.close()
    return imported, skipped
