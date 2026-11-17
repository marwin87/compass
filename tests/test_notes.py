import time

import pytest
from fastapi.testclient import TestClient

from compass import notes
from compass.db import connect
from compass.main import app


def add(c: TestClient, title: str, body: str = "") -> int:
    r = c.post("/api/notes", json={"title": title, "body": body})
    assert r.status_code == 201
    note_id: int = r.json()["id"]
    return note_id


def titles(c: TestClient, q: str = "") -> list[str]:
    r = c.get("/api/notes", params={"q": q})
    assert r.status_code == 200
    return [n["title"] for n in r.json()]


def test_create_then_get(authed: TestClient) -> None:
    note_id = add(authed, "Indeks w bazie", "B-tree przyspiesza zapytania")
    r = authed.get(f"/api/notes/{note_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Indeks w bazie"
    assert r.json()["body"] == "B-tree przyspiesza zapytania"


def test_unknown_note_is_404(authed: TestClient) -> None:
    assert authed.get("/api/notes/999").status_code == 404


@pytest.mark.parametrize("title", ["", "   ", "x" * 201])
def test_invalid_title_is_422(authed: TestClient, title: str) -> None:
    assert authed.post("/api/notes", json={"title": title}).status_code == 422


def test_prefix_match_in_title_and_body(authed: TestClient) -> None:
    add(authed, "Indeks w bazie", "o czyms innym")
    add(authed, "Transakcje", "ACID i izolacja")
    assert titles(authed, "ind") == ["Indeks w bazie"]
    assert titles(authed, "izol") == ["Transakcje"]


def test_match_ignores_case(authed: TestClient) -> None:
    add(authed, "Indeks")
    assert titles(authed, "INDEKS") == ["Indeks"]


def test_any_word_matches(authed: TestClient) -> None:
    add(authed, "Indeks")
    add(authed, "Transakcje")
    add(authed, "Fotosynteza")
    assert titles(authed, "indeks transakcje") == ["Transakcje", "Indeks"]


def test_no_match_is_empty(authed: TestClient) -> None:
    add(authed, "Indeks")
    assert titles(authed, "zzz") == []


def test_empty_query_lists_all_newest_first(authed: TestClient) -> None:
    add(authed, "pierwsza")
    add(authed, "druga")
    assert titles(authed) == ["druga", "pierwsza"]
    assert titles(authed, "   ") == ["druga", "pierwsza"]


@pytest.mark.parametrize("q", ['"', "'", "*", "-", "AND", "a OR", "(", "NEAR(", "col:"])
def test_special_characters_do_not_break_search(authed: TestClient, q: str) -> None:
    add(authed, "Indeks")
    assert authed.get("/api/notes", params={"q": q}).status_code == 200


def test_result_count_is_capped(authed: TestClient) -> None:
    for i in range(notes.LIMIT + 5):
        add(authed, f"nota {i}")
    assert len(titles(authed)) == notes.LIMIT


def test_api_requires_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        assert anon.get("/api/notes").status_code == 401
        assert anon.post("/api/notes", json={"title": "x"}).status_code == 401
        assert anon.get("/api/notes/1").status_code == 401


def test_search_in_5000_notes_is_fast(authed: TestClient) -> None:
    conn = connect()
    with conn:
        for i in range(5000):
            title, body = f"Nota {i} temat{i % 50}", f"lorem ipsum dolor {i}"
            cur = conn.execute(
                "INSERT INTO notes(title, body, created_at) VALUES (?, ?, 'x')",
                (title, body),
            )
            conn.execute(
                "INSERT INTO notes_fts(rowid, title, body) VALUES (?, ?, ?)",
                (cur.lastrowid, title, body),
            )
    conn.close()

    start = time.perf_counter()
    result = notes.list_notes("temat7 dol")
    elapsed = time.perf_counter() - start

    assert len(result) == notes.LIMIT
    assert elapsed < 0.5  # generous: real cost is a few ms; avoids flaky CI


def test_page_has_search_and_never_uses_inner_html(authed: TestClient) -> None:
    page = authed.get("/")
    assert page.status_code == 200
    assert 'id="q"' in page.text
    assert 'id="add"' in page.text
    assert 'id="edit"' in page.text
    assert 'id="editform"' in page.text
    assert 'id="eyes"' in page.text
    assert "innerHTML" not in page.text  # note content must only go in via textContent


def put(c: TestClient, note_id: int, title: str, body: str = "") -> int:
    status: int = c.put(
        f"/api/notes/{note_id}", json={"title": title, "body": body}
    ).status_code
    return status


def test_edit_replaces_text_and_keeps_created_at(authed: TestClient) -> None:
    note_id = add(authed, "Stary tytul", "stara tresc")
    created = authed.get(f"/api/notes/{note_id}").json()["created_at"]

    assert put(authed, note_id, "Nowy tytul", "nowa tresc") == 200
    got = authed.get(f"/api/notes/{note_id}").json()
    assert (got["title"], got["body"], got["created_at"]) == (
        "Nowy tytul",
        "nowa tresc",
        created,
    )


def test_edit_updates_search_index_for_title_and_body(authed: TestClient) -> None:
    note_id = add(authed, "Stary tytul", "stara tresc")
    put(authed, note_id, "Nowy tytul", "nowa tresc")
    assert titles(authed, "stary") == []
    assert titles(authed, "stara") == []
    assert titles(authed, "nowy") == ["Nowy tytul"]
    assert titles(authed, "nowa") == ["Nowy tytul"]


def test_edit_only_title_or_only_body(authed: TestClient) -> None:
    note_id = add(authed, "Tytul", "tresc")
    put(authed, note_id, "Inny", "tresc")
    assert titles(authed, "tytul") == []
    assert titles(authed, "tresc") == ["Inny"]
    put(authed, note_id, "Inny", "reszta")
    assert titles(authed, "tresc") == []
    assert titles(authed, "reszta") == ["Inny"]


def test_edit_keeps_position_and_does_not_duplicate(authed: TestClient) -> None:
    first = add(authed, "pierwsza")
    add(authed, "druga")
    put(authed, first, "pierwsza poprawiona")
    put(authed, first, "pierwsza poprawiona jeszcze raz")
    assert titles(authed) == ["druga", "pierwsza poprawiona jeszcze raz"]
    assert titles(authed, "pierwsza") == ["pierwsza poprawiona jeszcze raz"]


def test_edit_unknown_id_is_404(authed: TestClient) -> None:
    assert put(authed, 999, "x") == 404


def test_edit_with_invalid_title_changes_nothing(authed: TestClient) -> None:
    note_id = add(authed, "Tytul", "tresc")
    assert put(authed, note_id, "   ") == 422
    assert authed.get(f"/api/notes/{note_id}").json()["title"] == "Tytul"
    assert titles(authed, "tytul") == ["Tytul"]


def test_edit_requires_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        assert anon.put("/api/notes/1", json={"title": "x"}).status_code == 401
