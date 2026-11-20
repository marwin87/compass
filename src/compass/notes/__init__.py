import json
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from compass.db import index_note, session, unindex_note
from compass.notes import categories, summaries
from compass.search import fold, fuzzy_terms, rank_key, words

LIMIT = 50
CANDIDATES = 200  # notes fetched from the index (best bm25 first) before re-ranking
BM25_WEIGHTS = "10.0, 1.0, 20.0"  # title, body, tags
MAX_TITLE = 200
MAX_BODY = 20000
MAX_TAGS = 10
MAX_TAG_LEN = 30
COLUMNS = "n.id, n.title, n.body, n.created_at, n.category_id"


class Note(BaseModel):
    id: int
    title: str
    body: str
    created_at: str
    category_id: int
    tags: list[str] = []


@dataclass(frozen=True)
class ParsedSummary:
    """The AI summary of a note as an export file carries it."""

    text: str
    created_at: str
    stale: bool  # it was already out of date when the file was made


@dataclass(frozen=True)
class ParsedSource:
    """A note an answer cites. `note` is the id the note had in the file (None: it was deleted)."""

    note: int | None
    title: str


@dataclass(frozen=True)
class ParsedMessage:
    role: str  # "user" or "assistant"
    text: str
    created_at: str
    sources: tuple[ParsedSource, ...] = ()


@dataclass(frozen=True)
class ParsedConversation:
    title: str
    created_at: str
    messages: tuple[ParsedMessage, ...]


@dataclass(frozen=True)
class ParsedNote:
    """A note read from an export file, already validated (see `transfer.parse_export`)."""

    title: str
    body: str
    tags: tuple[str, ...]
    created_at: str  # kept exactly as written in the file
    when: datetime  # the same moment, timezone-aware, used only for ordering
    category: str | None = None  # a name; None means the default category
    summary: ParsedSummary | None = None
    file_id: int | None = (
        None  # the id the note had in the file: conversations point at it
    )


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
            category_id=r[4],
            tags=by_note[r[0]],
        )
        for r in rows
    ]


def _insert(
    conn: sqlite3.Connection,
    title: str,
    body: str,
    tags: Sequence[str],
    category: int,
) -> Note:
    """Insert one note inside the caller's transaction (`category` is an existing category id)."""
    clean = normalize_tags(tags)
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO notes(title, body, created_at, category_id) VALUES (?, ?, ?, ?)",
        (title, body, created_at, category),
    )
    note_id = cur.lastrowid
    assert note_id is not None
    _save_tags(conn, note_id, clean)
    index_note(conn, note_id, title, body, clean)
    return Note(
        id=note_id,
        title=title,
        body=body,
        created_at=created_at,
        category_id=category,
        tags=clean,
    )


def create_note(
    title: str, body: str, tags: Sequence[str] = (), category_id: int | None = None
) -> Note:
    with session() as conn, conn:
        return _insert(conn, title, body, tags, categories.resolve(conn, category_id))


def create_many(
    items: Sequence[tuple[str, str, Sequence[str], str | None]],
) -> int:
    """Add several notes (title, body, tags, category name) in one transaction: all or none.
    A category name that does not exist yet creates the category; None or a reserved name means the
    default."""
    with session() as conn, conn:
        for title, body, tags, category in items:
            _insert(conn, title, body, tags, categories.ensure(conn, category))
    return len(items)


def get_note(note_id: int) -> Note | None:
    with session() as conn:
        rows = conn.execute(
            f"SELECT {COLUMNS} FROM notes n WHERE n.id = ?", (note_id,)
        ).fetchall()
        found = _with_tags(conn, rows)
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


SORTS = ("title_asc", "title_desc", "date_asc", "date_desc")


def _when(created_at: str) -> datetime:
    """The creation moment as an aware datetime (imported dates may carry any offset)."""
    try:
        when = datetime.fromisoformat(created_at)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _sort_notes(items: list[Note], sort: str) -> None:
    """Sort in place: titles ignore case and accents (Polish letters sit next to their base letter)."""
    if sort.startswith("title"):
        items.sort(
            key=lambda n: (fold(n.title), n.title.lower(), n.id),
            reverse=sort == "title_desc",
        )
    else:
        items.sort(
            key=lambda n: (_when(n.created_at), n.id), reverse=sort == "date_desc"
        )


def list_notes(
    q: str = "",
    tags: Iterable[str] = (),
    category_id: int | None = None,
    sort: str | None = None,
) -> list[Note]:
    """Newest first without a query; otherwise the most relevant notes first.

    The tag filter (all tags) and the category filter (one category) combine with the text by AND.
    An explicit `sort` (see SORTS) replaces that default order, also while searching, and is applied
    before the result is cut to LIMIT.
    """
    if sort is not None and sort not in SORTS:
        raise ValueError(f"unknown sort: {sort}")
    tokens = words(q)
    tag_filter = _tag_filter(tags)
    with session() as conn:
        if not tokens:
            conditions: list[str] = []
            params: list[object] = []
            if tag_filter:
                conditions.append(f"n.id IN ({tag_filter[0]})")
                params += tag_filter[1]
            if category_id is not None:
                conditions.append("n.category_id = ?")
                params.append(category_id)
            where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
            if sort:
                rows = conn.execute(
                    f"SELECT {COLUMNS} FROM notes n {where}", params
                ).fetchall()
                found = _with_tags(conn, rows)
                _sort_notes(found, sort)
                return found[:LIMIT]
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
        if category_id is not None:
            sql += " AND rowid IN (SELECT id FROM notes WHERE category_id = ?)"
            params.append(category_id)
        sql += f" ORDER BY bm25(notes_fts, {BM25_WEIGHTS}) LIMIT ?"
        ids = [r[0] for r in conn.execute(sql, (*params, CANDIDATES))]
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT {COLUMNS} FROM notes n WHERE n.id IN ({marks})", ids
        ).fetchall()
        candidates = _with_tags(conn, rows)
    if sort:
        _sort_notes(candidates, sort)
    else:
        candidates.sort(
            key=lambda n: (*rank_key(tokens, n.title, n.body, n.tags, fuzzy), n.id),
            reverse=True,
        )
    return candidates[:LIMIT]


def export_all() -> list[Note]:
    """Every note with its tags, newest first, in one consistent query (no limit, no ranking)."""
    with session() as conn:
        rows = conn.execute(
            "SELECT n.id, n.title, n.body, n.created_at, n.category_id, "
            "group_concat(t.name, char(10)) "
            "FROM notes n "
            "LEFT JOIN note_tags nt ON nt.note_id = n.id "
            "LEFT JOIN tags t ON t.id = nt.tag_id "
            "GROUP BY n.id ORDER BY n.id DESC"
        ).fetchall()
    return [
        Note(
            id=r[0],
            title=r[1],
            body=r[2],
            created_at=r[3],
            category_id=r[4],
            tags=sorted(r[5].split("\n")) if r[5] else [],
        )
        for r in rows
    ]


def titles() -> list[str]:
    """The title of every note (an import uses them to warn about a note that already exists)."""
    with session() as conn:
        return [r[0] for r in conn.execute("SELECT title FROM notes")]


def list_tags() -> list[TagCount]:
    with session() as conn:
        rows = conn.execute(
            "SELECT t.name, COUNT(*) AS c FROM note_tags nt "
            "JOIN tags t ON t.id = nt.tag_id GROUP BY t.id ORDER BY c DESC, t.name"
        ).fetchall()
    return [TagCount(name=r[0], count=r[1]) for r in rows]


def update_note(
    note_id: int,
    title: str,
    body: str,
    tags: Sequence[str] = (),
    category_id: int | None = None,
) -> Note | None:
    """Replace title, body, tags and category (`None` = the default), keeping the index in step."""
    clean = normalize_tags(tags)
    with session() as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT created_at FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            return None
        category = categories.resolve(conn, category_id)
        conn.execute(
            "UPDATE notes SET title = ?, body = ?, category_id = ? WHERE id = ?",
            (title, body, category, note_id),
        )
        _save_tags(conn, note_id, clean)
        _drop_unused_tags(conn)
        index_note(conn, note_id, title, body, clean)
    return Note(
        id=note_id,
        title=title,
        body=body,
        created_at=row[0],
        category_id=category,
        tags=clean,
    )


def delete_note(note_id: int) -> bool:
    """Remove a note, its index entry and tags nobody uses any more."""
    with session() as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT id FROM notes WHERE id = ?", (note_id,)).fetchone()
        if row is None:
            return False
        unindex_note(conn, note_id)
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))  # cascades
        _drop_unused_tags(conn)
    return True


def replace_all(
    items: Sequence[ParsedNote],
    category_names: Sequence[str],
    conversations: Sequence[ParsedConversation] = (),
) -> int:
    """Make the database exactly what an export file says (all or nothing); returns the note count.

    Every existing note, tag and category is removed first, then the file's categories and notes
    are written, oldest first (an export is newest first) so the new ids follow creation order.
    Saved conversations are replaced too; their sources are pointed at the notes' new ids (a source
    whose note is not in the file keeps its title and shows as deleted).
    """
    # The file is newest first, so among equal times the later file position is the older note.
    ordered = [p for _, p in sorted(enumerate(items), key=lambda e: (e[1].when, -e[0]))]
    new_ids: dict[int, int] = {}  # id in the file -> id in the database
    with session() as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM notes_fts")
        conn.execute(
            "DELETE FROM conversations"
        )  # their sources would point at nothing
        conn.execute("DELETE FROM note_tags")
        conn.execute("DELETE FROM notes")
        conn.execute("DELETE FROM tags")
        conn.execute("DELETE FROM categories WHERE is_default = 0")
        for name in category_names:
            categories.ensure(conn, name)
        for p in ordered:
            cur = conn.execute(
                "INSERT INTO notes(title, body, created_at, category_id) VALUES (?, ?, ?, ?)",
                (
                    p.title,
                    p.body,
                    p.created_at,
                    categories.ensure(conn, p.category),
                ),
            )
            note_id = cur.lastrowid
            assert note_id is not None
            if p.file_id is not None:
                new_ids[p.file_id] = note_id
            _save_tags(conn, note_id, p.tags)
            index_note(conn, note_id, p.title, p.body, p.tags)
            if (
                p.summary
            ):  # a stale one gets a digest nothing matches, so it stays stale
                fresh = "" if p.summary.stale else summaries.digest(p.title, p.body)
                summaries.insert(
                    conn, note_id, p.summary.text, p.summary.created_at, fresh
                )
        for c in conversations:
            cid = conn.execute(
                "INSERT INTO conversations(title, created_at) VALUES (?, ?)",
                (c.title, c.created_at),
            ).lastrowid
            for m in c.messages:
                cited = [
                    {
                        "id": new_ids.get(s.note, 0) if s.note is not None else 0,
                        "title": s.title,
                    }
                    for s in m.sources
                ]  # 0 is never a note id: the source shows as deleted
                conn.execute(
                    "INSERT INTO chat_messages(conversation_id, role, text, sources, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (cid, m.role, m.text, json.dumps(cited), m.created_at),
                )
    return len(ordered)
