import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compass import notes
from compass.db import connect, index_note
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
            assert cur.lastrowid is not None
            index_note(conn, cur.lastrowid, title, body, ["tag" + str(i % 7)])
    conn.close()

    for query in ("temat7 dol", "tamat7 dolro", "ipsm loerm", "tag3"):
        start = time.perf_counter()
        result = notes.list_notes(query)
        elapsed = time.perf_counter() - start
        assert result, query
        assert len(result) <= notes.LIMIT
        assert elapsed < 0.5, (
            f"{query!r} took {elapsed:.3f}s"
        )  # generous: avoids flaky CI


def test_page_has_the_notes_ui_and_never_uses_inner_html(authed: TestClient) -> None:
    page = authed.get("/")
    assert page.status_code == 200
    for marker in (
        'id="q"',  # search box
        'id="tagbar"',  # tag filter
        'id="results"',
        'id="detail"',
        'id="new"',
        "Tagi (po przecinku)",  # tag input in the add and edit forms
        "Na pewno nadpisać?",  # edit needs a second confirmation
        "Na pewno usunąć?",  # so does delete
        'href="/settings"',  # the way to import, export and manage categories
        'id="catbar"',  # category filter in the side panel
        "Kategoria",  # the category field of the note forms
        "Nowa kategoria",  # quick add from the form
    ):
        assert marker in page.text, marker
    assert "innerHTML" not in page.text  # note content must only go in via textContent
    assert (
        "fonts.googleapis" not in page.text
    )  # no external requests: notes stay on this server


def test_login_page_is_styled_and_posts_to_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        page = anon.get("/login")
    assert page.status_code == 200
    assert 'action="/login"' in page.text
    assert 'name="password"' in page.text
    assert "fonts.googleapis" not in page.text


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


def delete(c: TestClient, note_id: int) -> int:
    status: int = c.delete(f"/api/notes/{note_id}").status_code
    return status


def test_deleted_note_is_gone_everywhere(authed: TestClient) -> None:
    gone = add(authed, "Indeks", "drzewo b-tree")
    kept = add(authed, "Transakcje", "izolacja")

    assert delete(authed, gone) == 204
    assert authed.get(f"/api/notes/{gone}").status_code == 404
    assert titles(authed) == ["Transakcje"]
    assert titles(authed, "indeks") == []
    assert titles(authed, "drzewo") == []
    assert titles(authed, "transakcje izolacja") == ["Transakcje"]
    assert authed.get(f"/api/notes/{kept}").status_code == 200


def test_delete_twice_and_unknown_id_are_404(authed: TestClient) -> None:
    note_id = add(authed, "Indeks")
    assert delete(authed, note_id) == 204
    assert delete(authed, note_id) == 404
    assert delete(authed, 999) == 404


def test_notes_work_after_a_delete_even_with_reused_id(authed: TestClient) -> None:
    old = add(authed, "stara nazwa", "stara tresc")
    delete(authed, old)
    new = add(authed, "nowa nazwa", "nowa tresc")  # SQLite may reuse the freed id
    assert titles(authed, "stara") == []
    assert titles(authed, "nowa") == ["nowa nazwa"]
    assert put(authed, new, "zmieniona", "tresc") == 200
    assert titles(authed, "zmieniona") == ["zmieniona"]


def test_delete_requires_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        assert anon.delete("/api/notes/1").status_code == 401


# --- tags -----------------------------------------------------------------


def add_t(c: TestClient, title: str, tags: list[str], body: str = "") -> int:
    r = c.post("/api/notes", json={"title": title, "body": body, "tags": tags})
    assert r.status_code == 201, r.text
    note_id: int = r.json()["id"]
    return note_id


def tag_titles(c: TestClient, *tags: str, q: str = "") -> list[str]:
    r = c.get("/api/notes", params={"q": q, "tag": list(tags)})
    assert r.status_code == 200
    return [n["title"] for n in r.json()]


def tag_counts(c: TestClient) -> dict[str, int]:
    r = c.get("/api/tags")
    assert r.status_code == 200
    return {t["name"]: t["count"] for t in r.json()}


def test_tags_are_normalised_deduplicated_and_sorted(authed: TestClient) -> None:
    note_id = add_t(authed, "n", ["  SQL ", "sql", "Soft   Skills", "", "  "])
    assert authed.get(f"/api/notes/{note_id}").json()["tags"] == ["soft skills", "sql"]


@pytest.mark.parametrize(
    "tags",
    [["x" * 31], ["a,b"], [f"t{i}" for i in range(11)]],
)
def test_invalid_tags_are_422(authed: TestClient, tags: list[str]) -> None:
    r = authed.post("/api/notes", json={"title": "n", "tags": tags})
    assert r.status_code == 422


def test_notes_without_tags_have_an_empty_list(authed: TestClient) -> None:
    note_id = add(authed, "bez tagow")
    assert authed.get(f"/api/notes/{note_id}").json()["tags"] == []
    assert tag_counts(authed) == {}


def test_list_returns_tags_for_each_note(authed: TestClient) -> None:
    add_t(authed, "a", ["x", "y"])
    add_t(authed, "b", [])
    got = {n["title"]: n["tags"] for n in authed.get("/api/notes").json()}
    assert got == {"a": ["x", "y"], "b": []}


def test_filter_by_one_tag_and_by_two_tags_is_and(authed: TestClient) -> None:
    add_t(authed, "sql tylko", ["sql"])
    add_t(authed, "rozmowa tylko", ["rozmowa"])
    add_t(authed, "oba", ["sql", "rozmowa"])
    assert tag_titles(authed, "sql") == ["oba", "sql tylko"]
    assert tag_titles(authed, "sql", "rozmowa") == ["oba"]
    assert tag_titles(authed, "sql", "sql") == ["oba", "sql tylko"]  # same tag twice


def test_filter_combines_with_text_and_normalises_the_tag(authed: TestClient) -> None:
    add_t(authed, "Indeks", ["sql"], "b-tree")
    add_t(authed, "Transakcje", ["sql"], "acid")
    add_t(authed, "Indeks w kuchni", ["gotowanie"])
    assert tag_titles(authed, "SQL", q="indeks") == ["Indeks"]
    assert tag_titles(authed, " Sql ") == ["Transakcje", "Indeks"]


def test_unknown_tag_matches_nothing(authed: TestClient) -> None:
    add_t(authed, "n", ["sql"])
    assert tag_titles(authed, "nie ma") == []


def test_tag_words_are_found_by_text_search(authed: TestClient) -> None:
    add_t(authed, "Indeks", ["rozmowa"])
    assert titles(authed, "rozmowa") == ["Indeks"]
    assert titles(authed, "rozm") == ["Indeks"]


def test_tag_counts_ordered_by_count_then_name(authed: TestClient) -> None:
    add_t(authed, "a", ["sql", "teoria"])
    add_t(authed, "b", ["sql", "api"])
    add_t(authed, "c", ["sql"])
    r = authed.get("/api/tags").json()
    assert r == [
        {"name": "sql", "count": 3},
        {"name": "api", "count": 1},
        {"name": "teoria", "count": 1},
    ]


def test_edit_replaces_tags_and_clearing_works(authed: TestClient) -> None:
    note_id = add_t(authed, "n", ["stary"])
    r = authed.put(f"/api/notes/{note_id}", json={"title": "n", "tags": ["Nowy"]})
    assert r.json()["tags"] == ["nowy"]
    assert tag_titles(authed, "stary") == []
    assert tag_titles(authed, "nowy") == ["n"]
    authed.put(f"/api/notes/{note_id}", json={"title": "n"})  # no tags field clears
    assert authed.get(f"/api/notes/{note_id}").json()["tags"] == []
    assert tag_counts(authed) == {}


def test_unused_tags_are_removed_but_shared_ones_survive(authed: TestClient) -> None:
    keep = add_t(authed, "keep", ["wspolny", "tylko-keep"])
    gone = add_t(authed, "gone", ["wspolny", "tylko-gone"])
    assert delete(authed, gone) == 204
    assert tag_counts(authed) == {"wspolny": 1, "tylko-keep": 1}
    assert authed.get(f"/api/notes/{keep}").json()["tags"] == ["tylko-keep", "wspolny"]
    conn = connect()
    assert conn.execute("SELECT name FROM tags ORDER BY name").fetchall() == [
        ("tylko-keep",),
        ("wspolny",),
    ]
    conn.close()


def test_deleting_a_note_leaves_no_link_rows(authed: TestClient) -> None:
    note_id = add_t(authed, "n", ["a", "b"])
    delete(authed, note_id)
    conn = connect()
    assert conn.execute("SELECT COUNT(*) FROM note_tags").fetchone() == (0,)
    assert conn.execute("SELECT COUNT(*) FROM tags").fetchone() == (0,)
    conn.close()


def test_old_database_without_tag_tables_still_works(db_file: Path) -> None:
    import sqlite3

    db_file.parent.mkdir(parents=True, exist_ok=True)
    old = sqlite3.connect(db_file)
    old.executescript(
        "CREATE TABLE notes(id INTEGER PRIMARY KEY, title TEXT NOT NULL, "
        "body TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);"
        "INSERT INTO notes(title, created_at) VALUES ('stara', 'x');"
    )
    old.close()
    assert [n.title for n in notes.list_notes()] == ["stara"]
    assert notes.list_notes()[0].tags == []
    assert notes.create_note("nowa", "", ["t"]).tags == ["t"]


def test_tags_require_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        assert anon.get("/api/tags").status_code == 401


# --- folded index (S-06 phase 1) ---------------------------------------------


def test_missing_polish_letters_still_find_the_note(authed: TestClient) -> None:
    add(
        authed,
        "Złożoność obliczeniowa",
        "Wyszukiwanie binarne działa w czasie O(log n)",
    )
    assert titles(authed, "zlozonosc") == ["Złożoność obliczeniowa"]
    assert titles(authed, "ZŁOŻONOŚĆ") == ["Złożoność obliczeniowa"]
    assert titles(authed, "dziala") == ["Złożoność obliczeniowa"]


def test_polish_letters_find_a_note_typed_without_them(authed: TestClient) -> None:
    add(authed, "Zlozonosc obliczeniowa")
    assert titles(authed, "złożoność") == ["Zlozonosc obliczeniowa"]


def test_polish_letters_in_tags_are_searchable_both_ways(authed: TestClient) -> None:
    add_t(authed, "n", ["wydajność"])
    assert titles(authed, "wydajnosc") == ["n"]
    assert titles(authed, "wydajność") == ["n"]


def test_edit_and_delete_leave_no_stale_words_in_the_index(authed: TestClient) -> None:
    note_id = add_t(authed, "Stary tytuł", ["oldtag"], "stara treść")
    put_tags = authed.put(
        f"/api/notes/{note_id}",
        json={"title": "Nowy tytuł", "body": "nowa treść", "tags": ["newtag"]},
    )
    assert put_tags.status_code == 200
    for stale in ("stary", "stara", "oldtag"):
        assert titles(authed, stale) == []
    assert titles(authed, "nowy") == ["Nowy tytuł"]
    assert titles(authed, "nowa") == ["Nowy tytuł"]
    assert titles(authed, "newtag") == ["Nowy tytuł"]
    delete(authed, note_id)
    for gone in ("nowy", "nowa", "newtag"):
        assert titles(authed, gone) == []


def test_clearing_tags_removes_their_words_from_the_index(authed: TestClient) -> None:
    note_id = add_t(authed, "n", ["rozmowa"])
    authed.put(f"/api/notes/{note_id}", json={"title": "n"})
    assert titles(authed, "rozmowa") == []


OLD_SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE notes(id INTEGER PRIMARY KEY, title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE tags(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE note_tags(note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag_id));
CREATE VIRTUAL TABLE notes_fts USING fts5(title, body, content='notes', content_rowid='id');
INSERT INTO notes(id, title, body, created_at) VALUES (1, 'Złożoność', 'czas O(n)', 'x');
INSERT INTO notes_fts(rowid, title, body) VALUES (1, 'Złożoność', 'czas O(n)');
INSERT INTO notes(id, title, body, created_at) VALUES (2, 'Indeks', 'b-tree', 'x');
INSERT INTO notes_fts(rowid, title, body) VALUES (2, 'Indeks', 'b-tree');
INSERT INTO tags(id, name) VALUES (1, 'sql');
INSERT INTO note_tags(note_id, tag_id) VALUES (2, 1);
"""


def test_old_index_is_migrated_once(db_file: Path) -> None:
    import sqlite3

    db_file.parent.mkdir(parents=True, exist_ok=True)
    old = sqlite3.connect(db_file)
    old.executescript(OLD_SCHEMA)
    old.close()

    assert [n.title for n in notes.list_notes("zlozonosc")] == ["Złożoność"]
    assert [n.title for n in notes.list_notes("sql")] == ["Indeks"]  # tag is searchable
    assert [n.title for n in notes.list_notes("indek")] == ["Indeks"]

    conn = connect()
    assert conn.execute(
        "SELECT value FROM meta WHERE key='fts_version'"
    ).fetchone() == ("2",)
    conn.execute("DELETE FROM notes_fts WHERE rowid = 2")  # a rebuild would restore it
    conn.commit()
    conn.close()
    assert notes.list_notes("indek") == []  # second connect did not rebuild


# --- ranking (S-06 phase 2) ---------------------------------------------------


def test_title_match_beats_a_newer_body_only_match(authed: TestClient) -> None:
    add(authed, "Indeks", "")
    add(authed, "Transakcje", "o indeks w bazie")
    assert titles(authed, "indeks") == ["Indeks", "Transakcje"]


def test_exact_tag_beats_a_title_match(authed: TestClient) -> None:
    add_t(authed, "Transakcje", ["sql"])
    add(authed, "SQL basics")  # newer, has the word in its title but no such tag
    assert titles(authed, "sql") == ["Transakcje", "SQL basics"]


def test_tag_equal_to_the_whole_multi_word_query_is_exact(authed: TestClient) -> None:
    add_t(authed, "Rozmowa", ["soft skills"])
    add(authed, "Soft skills intro")
    assert titles(authed, "soft skills") == ["Rozmowa", "Soft skills intro"]


def test_partial_tag_word_is_weaker_than_a_title_match(authed: TestClient) -> None:
    add_t(authed, "Rozmowa", ["soft skills"])
    add(authed, "Soft drinks")
    assert titles(authed, "soft") == ["Soft drinks", "Rozmowa"]


def test_more_matched_words_beat_a_single_title_hit(authed: TestClient) -> None:
    add(authed, "Transakcje", "indeks baza")  # both words, body only
    add(authed, "Indeks")  # one word, in the title, newer
    assert titles(authed, "indeks baza") == ["Transakcje", "Indeks"]


def test_exact_word_beats_a_prefix_in_the_same_field(authed: TestClient) -> None:
    add(authed, "Indeks")
    add(authed, "Indeksy")  # newer, only a prefix match
    assert titles(authed, "indeks") == ["Indeks", "Indeksy"]


def test_equal_relevance_is_newest_first(authed: TestClient) -> None:
    add(authed, "Indeks pierwszy")
    add(authed, "Indeks drugi")
    assert titles(authed, "indeks") == ["Indeks drugi", "Indeks pierwszy"]


def test_tag_filter_still_ands_with_ranked_text(authed: TestClient) -> None:
    add_t(authed, "Indeks", ["sql"])
    add_t(authed, "Indeks kuchenny", ["gotowanie"])
    add_t(authed, "Transakcje", ["sql"], "indeks")
    assert tag_titles(authed, "sql", q="indeks") == ["Indeks", "Transakcje"]


def test_an_exact_tag_note_survives_the_candidate_cut(authed: TestClient) -> None:
    add_t(authed, "Ten z tagiem", ["sql"])
    for i in range(notes.CANDIDATES + 100):
        add(authed, f"nota {i}", "sql " * 5)
    assert titles(authed, "sql")[0] == "Ten z tagiem"


# --- typo tolerance (S-06 phase 3) -------------------------------------------


def test_typos_still_find_the_note(authed: TestClient) -> None:
    add(authed, "Indeks w bazie danych")
    add(authed, "Złożoność obliczeniowa")
    assert titles(authed, "indkes") == ["Indeks w bazie danych"]  # swapped letters
    assert titles(authed, "indekt") == ["Indeks w bazie danych"]  # wrong letter
    assert titles(authed, "zlozonsoc") == [
        "Złożoność obliczeniowa"
    ]  # missing PL + typo


def test_two_typos_are_tolerated_only_in_long_words(authed: TestClient) -> None:
    add(authed, "Złożoność obliczeniowa")
    add(authed, "Indeks")
    assert titles(authed, "zlzonosc") == ["Złożoność obliczeniowa"]  # 1 deletion
    assert titles(authed, "zlzonsoc") == [
        "Złożoność obliczeniowa"
    ]  # 8 letters, 2 edits
    assert titles(authed, "zlzonoc") == []  # 7 letters, 2 edits: too far
    assert titles(authed, "indks") == ["Indeks"]  # 1 edit
    assert titles(authed, "idks") == []  # 2 edits in a 4-letter word: too far


def test_short_words_are_not_corrected(authed: TestClient) -> None:
    add(authed, "SQL basics")
    add(authed, "Zapytanie sqr")
    assert titles(authed, "sql") == ["SQL basics"]  # no fuzzy hit on "sqr"


def test_a_typo_in_a_tag_finds_the_note(authed: TestClient) -> None:
    add_t(authed, "Rozmowa o prace", ["wydajność"])
    assert titles(authed, "wydajnosc") == ["Rozmowa o prace"]
    assert titles(authed, "wydajnsoc") == ["Rozmowa o prace"]


def test_typo_hits_rank_below_exact_and_prefix_hits_in_the_same_field(
    authed: TestClient,
) -> None:
    add(authed, "Indkes")  # typo, oldest
    add(authed, "Indeksy")  # prefix
    add(authed, "Indeks")  # exact
    add(authed, "Indekt")  # typo, newest
    assert titles(authed, "indeks") == ["Indeks", "Indeksy", "Indekt", "Indkes"]


def test_a_typo_in_the_title_still_beats_an_exact_word_in_the_body(
    authed: TestClient,
) -> None:
    add(authed, "Transakcje", "indeks")  # exact, but body only
    add(authed, "Indkes")  # title typo: the field rule wins
    assert titles(authed, "indeks") == ["Indkes", "Transakcje"]


def test_typos_still_and_with_the_tag_filter(authed: TestClient) -> None:
    add_t(authed, "Indeks", ["sql"])
    add_t(authed, "Indeks kuchenny", ["gotowanie"])
    assert tag_titles(authed, "sql", q="indkes") == ["Indeks"]
