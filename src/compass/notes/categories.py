"""Categories: a managed list; every note belongs to exactly one.

Category 1 is the built-in default (stored with an empty name, shown translated by the page).
Names are unique ignoring case and diacritics (compared through `search.fold`). Errors are
`CategoryError` with a machine-readable `code`; the API turns them into HTTP errors and the
page translates the codes.
"""

import sqlite3

from pydantic import BaseModel

from compass.db import DEFAULT_CATEGORY_ID, session
from compass.search import fold

MAX_NAME = 40
# Names that would look like the default category (both languages) cannot be created.
RESERVED_KEYS = frozenset({"", "bez kategorii", "uncategorized"})


class CategoryError(Exception):
    def __init__(self, code: str, **info: object) -> None:
        super().__init__(code)
        self.code = code
        self.info = info


class Category(BaseModel):
    id: int
    name: str  # empty for the default category: the page shows its translated label
    default: bool
    count: int


def normalize(name: str) -> tuple[str, str]:
    """Return (display name, unique key); raise `name_invalid` or `name_reserved`."""
    clean = " ".join(name.split())
    if not 1 <= len(clean) <= MAX_NAME:
        raise CategoryError("name_invalid")
    key = fold(clean)
    if key in RESERVED_KEYS:
        raise CategoryError("name_reserved")
    return clean, key


def _count(conn: sqlite3.Connection, category_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM notes WHERE category_id = ?", (category_id,)
    ).fetchone()
    return int(row[0])


def list_categories() -> list[Category]:
    """Every category with its note count: alphabetical, the default last."""
    with session() as conn:
        rows = conn.execute(
            "SELECT c.id, c.name, c.key, c.is_default, COUNT(n.id) FROM categories c "
            "LEFT JOIN notes n ON n.category_id = c.id GROUP BY c.id"
        ).fetchall()
    rows.sort(key=lambda r: (bool(r[3]), r[2]))
    return [Category(id=r[0], name=r[1], default=bool(r[3]), count=r[4]) for r in rows]


def create(name: str) -> Category:
    clean, key = normalize(name)
    with session() as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        taken = conn.execute(
            "SELECT id FROM categories WHERE key = ?", (key,)
        ).fetchone()
        if taken:
            raise CategoryError("name_taken", id=taken[0])
        cur = conn.execute(
            "INSERT INTO categories(name, key) VALUES (?, ?)", (clean, key)
        )
        category_id = cur.lastrowid
        assert category_id is not None
    return Category(id=category_id, name=clean, default=False, count=0)


def rename(category_id: int, name: str) -> Category:
    clean, key = normalize(name)
    with session() as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT is_default FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None:
            raise CategoryError("not_found")
        if row[0]:
            raise CategoryError("default_category")
        taken = conn.execute(
            "SELECT id FROM categories WHERE key = ? AND id != ?",
            (key, category_id),
        ).fetchone()
        if taken:
            raise CategoryError("name_taken", id=taken[0])
        conn.execute(
            "UPDATE categories SET name = ?, key = ? WHERE id = ?",
            (clean, key, category_id),
        )
        count = _count(conn, category_id)
    return Category(id=category_id, name=clean, default=False, count=count)


def delete(category_id: int) -> None:
    """Delete an empty, non-default category (a category with notes is never deleted)."""
    with session() as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT is_default FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None:
            raise CategoryError("not_found")
        if row[0]:
            raise CategoryError("default_category")
        count = _count(conn, category_id)
        if count:
            raise CategoryError("not_empty", count=count)
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def resolve(conn: sqlite3.Connection, category_id: int | None) -> int:
    """The category a note will get: `None` means the default; an unknown id is an error."""
    if category_id is None:
        return DEFAULT_CATEGORY_ID
    if (
        conn.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone()
        is None
    ):
        raise CategoryError("invalid_category")
    return category_id


def ensure(conn: sqlite3.Connection, name: str | None) -> int:
    """Id of the category called `name`, creating it when missing (used by import).

    `None`, an empty name and the default's labels (either language) mean the default.
    """
    if name is None:
        return DEFAULT_CATEGORY_ID
    clean = " ".join(name.split())
    key = fold(clean)
    if key in RESERVED_KEYS:
        return DEFAULT_CATEGORY_ID
    if len(clean) > MAX_NAME:
        raise CategoryError("name_invalid")
    found = conn.execute("SELECT id FROM categories WHERE key = ?", (key,)).fetchone()
    if found:
        return int(found[0])
    cur = conn.execute("INSERT INTO categories(name, key) VALUES (?, ?)", (clean, key))
    assert cur.lastrowid is not None
    return cur.lastrowid
