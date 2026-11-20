import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass.db import connect
from compass.main import app
from compass.notes import categories

DEFAULT = 1


def cats(c: TestClient) -> list[dict[str, Any]]:
    r = c.get("/api/categories")
    assert r.status_code == 200
    rows: list[dict[str, Any]] = r.json()
    return rows


def make(c: TestClient, name: str) -> int:
    r = c.post("/api/categories", json={"name": name})
    assert r.status_code == 201, r.text
    category_id: int = r.json()["id"]
    return category_id


def note(
    c: TestClient, title: str, category_id: int | None = None, **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": title, **extra}
    if category_id is not None:
        body["category_id"] = category_id
    r = c.post("/api/notes", json=body)
    assert r.status_code == 201, r.text
    created: dict[str, Any] = r.json()
    return created


def titles(
    c: TestClient, q: str = "", category_id: int | None = None, *tags: str
) -> list[str]:
    params: dict[str, Any] = {"q": q, "tag": list(tags)}
    if category_id is not None:
        params["category_id"] = category_id
    return [n["title"] for n in c.get("/api/notes", params=params).json()]


def error(r: Any) -> dict[str, Any]:
    detail: dict[str, Any] = r.json()["detail"]
    return detail


def test_the_default_category_exists_on_a_fresh_database(authed: TestClient) -> None:
    assert cats(authed) == [{"id": DEFAULT, "name": "", "default": True, "count": 0}]


def test_create_rename_delete_and_list_with_counts(authed: TestClient) -> None:
    a, b = make(authed, "Bazy danych"), make(authed, "algorytmy")
    note(authed, "n1", a)
    note(authed, "n2", a)
    note(authed, "n3", b)
    note(authed, "n4")  # no category: the default
    listing = cats(authed)
    assert [(c["name"], c["count"], c["default"]) for c in listing] == [
        ("algorytmy", 1, False),
        ("Bazy danych", 2, False),
        ("", 1, True),  # alphabetical, the default last
    ]
    renamed = authed.put(f"/api/categories/{b}", json={"name": "  Struktury   danych "})
    assert renamed.status_code == 200
    assert renamed.json() == {
        "id": b,
        "name": "Struktury danych",
        "default": False,
        "count": 1,
    }
    assert authed.delete(f"/api/categories/{make(authed, 'Pusta')}").status_code == 204
    assert "Pusta" not in [c["name"] for c in cats(authed)]


@pytest.mark.parametrize("name", ["", "   ", "x" * 41])
def test_invalid_names(authed: TestClient, name: str) -> None:
    r = authed.post("/api/categories", json={"name": name})
    assert r.status_code == 422 and error(r)["code"] == "name_invalid"


@pytest.mark.parametrize(
    "name", ["Bez kategorii", "bez  KATEGORII", "Uncategorized", "UNCATEGORIZED "]
)
def test_reserved_names(authed: TestClient, name: str) -> None:
    r = authed.post("/api/categories", json={"name": name})
    assert r.status_code == 422 and error(r)["code"] == "name_reserved"


def test_a_forty_character_name_is_fine_and_whitespace_is_collapsed(
    authed: TestClient,
) -> None:
    long_name = "k" * 40
    assert authed.post("/api/categories", json={"name": long_name}).status_code == 201
    r = authed.post("/api/categories", json={"name": "  Dom   i   ogród "})
    assert r.json()["name"] == "Dom i ogród"


@pytest.mark.parametrize("again", ["Łódź", "łódź", "LODZ", "lodz", " Lodz  "])
def test_names_are_unique_ignoring_case_and_diacritics(
    authed: TestClient, again: str
) -> None:
    first = make(authed, "Łódź")
    r = authed.post("/api/categories", json={"name": again})
    assert r.status_code == 409
    assert error(r) == {"code": "name_taken", "id": first}  # the existing id comes back


def test_rename_rules(authed: TestClient) -> None:
    a, b = make(authed, "Alfa"), make(authed, "Beta")
    clash = authed.put(f"/api/categories/{b}", json={"name": "ALFA"})
    assert clash.status_code == 409 and error(clash) == {"code": "name_taken", "id": a}
    assert (
        authed.put(f"/api/categories/{a}", json={"name": "ALFA"}).status_code == 200
    )  # same one, new case
    assert (
        authed.put(f"/api/categories/{a}", json={"name": "Uncategorized"}).status_code
        == 422
    )
    assert authed.put(f"/api/categories/{a}", json={"name": ""}).status_code == 422
    missing = authed.put("/api/categories/999", json={"name": "X"})
    assert missing.status_code == 404 and error(missing)["code"] == "not_found"


def test_the_default_cannot_be_renamed_or_deleted(authed: TestClient) -> None:
    for r in (
        authed.put(f"/api/categories/{DEFAULT}", json={"name": "Inna"}),
        authed.delete(f"/api/categories/{DEFAULT}"),
    ):
        assert r.status_code == 409 and error(r)["code"] == "default_category"
    assert cats(authed)[0]["default"] is True


def test_a_category_with_notes_cannot_be_deleted_until_it_is_empty(
    authed: TestClient,
) -> None:
    c = make(authed, "Zajęta")
    first, second = note(authed, "a", c), note(authed, "b", c)
    r = authed.delete(f"/api/categories/{c}")
    assert r.status_code == 409 and error(r) == {"code": "not_empty", "count": 2}
    authed.delete(f"/api/notes/{first['id']}")
    assert error(authed.delete(f"/api/categories/{c}"))["count"] == 1
    authed.put(
        f"/api/notes/{second['id']}", json={"title": "b"}
    )  # no category: back to the default
    assert authed.delete(f"/api/categories/{c}").status_code == 204
    missing = authed.delete(f"/api/categories/{c}")
    assert missing.status_code == 404


def test_a_note_without_a_category_lands_in_the_default(authed: TestClient) -> None:
    assert note(authed, "bez")["category_id"] == DEFAULT


def test_a_note_can_be_created_in_a_category_and_moved(authed: TestClient) -> None:
    a, b = make(authed, "A"), make(authed, "B")
    created = note(authed, "n", a)
    assert authed.get(f"/api/notes/{created['id']}").json()["category_id"] == a
    moved = authed.put(
        f"/api/notes/{created['id']}", json={"title": "n", "category_id": b}
    )
    assert moved.status_code == 200 and moved.json()["category_id"] == b
    assert authed.get(f"/api/notes/{created['id']}").json()["category_id"] == b
    reset = authed.put(
        f"/api/notes/{created['id']}", json={"title": "n"}
    )  # full replacement
    assert reset.json()["category_id"] == DEFAULT


@pytest.mark.parametrize("bad", [999, 0, -1])
def test_an_unknown_category_is_refused_for_create_and_update(
    authed: TestClient, bad: int
) -> None:
    r = authed.post("/api/notes", json={"title": "n", "category_id": bad})
    assert r.status_code == 422 and error(r)["code"] == "invalid_category"
    created = note(authed, "ok")
    r = authed.put(
        f"/api/notes/{created['id']}", json={"title": "ok", "category_id": bad}
    )
    assert r.status_code == 422 and error(r)["code"] == "invalid_category"
    assert (
        authed.get(f"/api/notes/{created['id']}").json()["category_id"] == DEFAULT
    )  # nothing changed
    assert (
        len(authed.get("/api/notes").json()) == 1
    )  # and the refused create left nothing behind


def test_filter_by_category_alone_and_with_text_and_tags(authed: TestClient) -> None:
    sql, other = make(authed, "SQL"), make(authed, "Inne")
    note(authed, "Indeks", sql, body="b-tree", tags=["rozmowa"])
    note(authed, "Transakcje", sql, body="acid", tags=["teoria"])
    note(authed, "Indeks kuchenny", other, tags=["rozmowa"])
    note(authed, "Luźna")
    assert titles(authed, "", sql) == ["Transakcje", "Indeks"]  # no query: newest first
    assert titles(authed, "", other) == ["Indeks kuchenny"]
    assert titles(authed, "", DEFAULT) == ["Luźna"]
    assert titles(authed, "indeks") == [
        "Indeks kuchenny",
        "Indeks",
    ]  # no category filter: all
    assert titles(authed, "indeks", sql) == ["Indeks"]  # ranked text search, filtered
    assert titles(authed, "indkes", sql) == [
        "Indeks"
    ]  # a typo still works inside a category
    assert titles(authed, "", sql, "rozmowa") == ["Indeks"]  # AND with tags
    assert titles(authed, "indeks", other, "rozmowa") == ["Indeks kuchenny"]
    assert titles(authed, "indeks", other, "teoria") == []
    assert titles(authed, "", 999) == []  # an unknown id just matches nothing


def test_counts_follow_creating_moving_and_deleting_notes(authed: TestClient) -> None:
    a, b = make(authed, "A"), make(authed, "B")
    one, two = note(authed, "1", a), note(authed, "2", a)

    def counts() -> dict[str, int]:
        return {c["name"]: c["count"] for c in cats(authed)}

    assert counts() == {"A": 2, "B": 0, "": 0}
    authed.put(f"/api/notes/{two['id']}", json={"title": "2", "category_id": b})
    assert counts() == {"A": 1, "B": 1, "": 0}
    authed.delete(f"/api/notes/{one['id']}")
    assert counts() == {"A": 0, "B": 1, "": 0}


def test_no_note_ever_points_at_a_missing_category(authed: TestClient) -> None:
    a = make(authed, "A")
    note(authed, "1", a)
    authed.delete(f"/api/categories/{a}")  # refused: not empty
    authed.post("/api/notes", json={"title": "x", "category_id": 999})  # refused
    conn = connect()
    orphans = conn.execute(
        "SELECT COUNT(*) FROM notes WHERE category_id NOT IN (SELECT id FROM categories)"
    ).fetchone()
    conn.close()
    assert orphans == (0,)


def test_ensure_resolves_names_for_import(authed: TestClient) -> None:
    conn = connect()
    with conn:
        assert categories.ensure(conn, None) == DEFAULT
        assert categories.ensure(conn, "") == DEFAULT
        assert categories.ensure(conn, "Bez kategorii") == DEFAULT
        assert categories.ensure(conn, "uncategorized") == DEFAULT
        new = categories.ensure(conn, " Nowa  kategoria ")
        assert categories.ensure(conn, "NOWA KATEGORIA") == new  # found, not duplicated
    conn.close()
    assert [c["name"] for c in cats(authed)] == ["Nowa kategoria", ""]


def test_old_notes_with_no_category_column_migrate_into_the_default(
    db_file: Path,
) -> None:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    old = sqlite3.connect(db_file)  # a database made before categories existed
    old.executescript(
        """
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE notes(id INTEGER PRIMARY KEY, title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE tags(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE note_tags(note_id INTEGER NOT NULL, tag_id INTEGER NOT NULL,
            PRIMARY KEY (note_id, tag_id));
        INSERT INTO notes(id, title, body, created_at) VALUES (1, 'Złożoność', 'czas', '2026-01-01T00:00:00+00:00');
        INSERT INTO notes(id, title, body, created_at) VALUES (2, 'Indeks', 'b-tree', '2026-01-02T00:00:00+00:00');
        INSERT INTO tags(id, name) VALUES (1, 'sql');
        INSERT INTO note_tags(note_id, tag_id) VALUES (2, 1);
        """
    )
    old.close()

    with TestClient(
        app, follow_redirects=False
    ) as c:  # starting the app opens and migrates it
        assert c.post("/login", data={"password": "test-password"}).status_code == 303
        listing = c.get("/api/notes").json()
        assert [(n["title"], n["category_id"]) for n in listing] == [
            ("Indeks", DEFAULT),
            ("Złożoność", DEFAULT),
        ]
        assert titles(c, "zlozonosc") == ["Złożoność"]  # the search index was built too
        assert titles(c, "", DEFAULT, "sql") == ["Indeks"]
        assert cats(c) == [{"id": DEFAULT, "name": "", "default": True, "count": 2}]
        connect().close()  # a second connect changes nothing
        assert cats(c) == [{"id": DEFAULT, "name": "", "default": True, "count": 2}]
        created = note(c, "nowa po migracji", make(c, "Po"))
        assert created["category_id"] != DEFAULT
    conn = connect()
    assert "category_id" in [row[1] for row in conn.execute("PRAGMA table_info(notes)")]
    conn.close()


def test_connect_twice_is_idempotent(authed: TestClient) -> None:
    for _ in range(3):
        connect().close()
    assert len(cats(authed)) == 1


def test_categories_require_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        assert anon.get("/api/categories").status_code == 401
        assert anon.post("/api/categories", json={"name": "X"}).status_code == 401
        assert anon.put("/api/categories/1", json={"name": "X"}).status_code == 401
        assert anon.delete("/api/categories/2").status_code == 401
