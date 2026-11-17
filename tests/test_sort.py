from fastapi.testclient import TestClient

from compass.db import connect, index_note
from compass.notes import _save_tags


def seed(rows: list[tuple[str, str, list[str], str]], category_id: int = 1) -> None:
    """Insert notes straight into the database (title, body, tags, created_at)."""
    conn = connect()
    with conn:
        for title, body, tags, created_at in rows:
            cur = conn.execute(
                "INSERT INTO notes(title, body, created_at, category_id) VALUES (?, ?, ?, ?)",
                (title, body, created_at, category_id),
            )
            assert cur.lastrowid is not None
            _save_tags(conn, cur.lastrowid, tags)
            index_note(conn, cur.lastrowid, title, body, tags)
    conn.close()


def titles(c: TestClient, **params: object) -> list[str]:
    r = c.get("/api/notes", params=params)
    assert r.status_code == 200
    return [n["title"] for n in r.json()]


def test_title_sort_ignores_case_and_places_polish_letters_by_their_base_letter(
    authed: TestClient,
) -> None:
    seed(
        [
            ("zebra", "", [], "2026-01-01T00:00:00+00:00"),
            ("Łódź", "", [], "2026-01-02T00:00:00+00:00"),
            ("ćma", "", [], "2026-01-03T00:00:00+00:00"),
            ("Cebula", "", [], "2026-01-04T00:00:00+00:00"),
            ("Ala", "", [], "2026-01-05T00:00:00+00:00"),
            ("ąbc", "", [], "2026-01-06T00:00:00+00:00"),
        ]
    )
    assert titles(authed, sort="title_asc") == [
        "ąbc",
        "Ala",
        "Cebula",
        "ćma",
        "Łódź",
        "zebra",
    ]
    assert titles(authed, sort="title_desc") == list(
        reversed(titles(authed, sort="title_asc"))
    )


def test_title_sort_is_stable_for_equal_titles(authed: TestClient) -> None:
    seed(
        [
            ("Ta sama", "a", [], "2026-01-01T00:00:00+00:00"),
            ("ta sama", "b", [], "2026-01-02T00:00:00+00:00"),
        ]
    )
    r = authed.get("/api/notes", params={"sort": "title_asc"}).json()
    assert [n["body"] for n in r] == [
        "a",
        "b",
    ]  # ties fall back to the title's case, then to the id


def test_date_order_with_offsets_is_chronological(authed: TestClient) -> None:
    seed(
        [
            ("a", "", [], "2026-03-01T12:00:00+00:00"),  # 12:00 UTC
            ("b", "", [], "2026-03-01T13:00:00+05:00"),  # 08:00 UTC
            ("c", "", [], "2026-03-01T09:00:00-05:00"),  # 14:00 UTC
            (
                "bez strefy",
                "",
                [],
                "2026-02-28",
            ),  # a date without time or offset counts as UTC midnight
        ]
    )
    assert titles(authed, sort="date_asc") == ["bez strefy", "b", "a", "c"]
    assert titles(authed, sort="date_desc") == ["c", "a", "b", "bez strefy"]


def test_default_order_is_unchanged_newest_first(authed: TestClient) -> None:
    seed(
        [
            ("pierwsza", "", [], "2026-01-01T00:00:00+00:00"),
            ("druga", "", [], "2026-01-02T00:00:00+00:00"),
        ]
    )
    assert titles(authed) == ["druga", "pierwsza"]
    assert (
        authed.get("/api/notes", params={"sort": ""}).status_code == 422
    )  # "no sort" means leaving it out


def test_sort_combines_with_tag_and_category_filters(authed: TestClient) -> None:
    other = authed.post("/api/categories", json={"name": "Dom"}).json()["id"]
    seed(
        [
            ("b", "", ["x"], "2026-01-01T00:00:00+00:00"),
            ("a", "", ["x"], "2026-01-02T00:00:00+00:00"),
            ("c", "", [], "2026-01-03T00:00:00+00:00"),
        ]
    )
    seed([("d", "", ["x"], "2026-01-04T00:00:00+00:00")], category_id=other)
    assert titles(authed, sort="title_asc", tag="x") == ["a", "b", "d"]
    assert titles(authed, sort="title_desc", category_id=other) == ["d"]
    assert titles(authed, sort="title_asc", tag="x", category_id=1) == ["a", "b"]


def test_sort_overrides_relevance_while_searching(authed: TestClient) -> None:
    seed(
        [
            (
                "Zebra",
                "indeks indeks indeks",
                ["indeks"],
                "2026-01-01T00:00:00+00:00",
            ),  # most relevant
            ("Alfa", "wspomina indeks raz", [], "2026-01-02T00:00:00+00:00"),
            ("Mama", "indeks", [], "2026-01-03T00:00:00+00:00"),
        ]
    )
    assert titles(authed, q="indeks")[0] == "Zebra"  # relevance by default
    assert titles(authed, q="indeks", sort="title_asc") == ["Alfa", "Mama", "Zebra"]
    assert titles(authed, q="indeks", sort="date_desc") == ["Mama", "Alfa", "Zebra"]


def test_the_sort_happens_before_the_result_is_cut_to_fifty(authed: TestClient) -> None:
    seed(
        [
            (f"Nota {i:03d}", "", [], f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00")
            for i in range(70)
        ]
    )
    first = titles(authed, sort="title_asc")
    assert len(first) == 50 and first[0] == "Nota 000" and first[-1] == "Nota 049"
    oldest = titles(authed, sort="date_asc")
    assert oldest[0] == "Nota 000"
    assert titles(authed)[0] == "Nota 069"  # default: the 50 newest


def test_an_unknown_sort_is_rejected(authed: TestClient) -> None:
    assert authed.get("/api/notes", params={"sort": "random"}).status_code == 422
    assert authed.get("/api/notes", params={"sort": "TITLE_ASC"}).status_code == 422


def test_sort_requires_login() -> None:
    from compass.main import app

    with TestClient(app, follow_redirects=False) as anon:
        assert anon.get("/api/notes", params={"sort": "title_asc"}).status_code == 401
