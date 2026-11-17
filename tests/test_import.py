import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass import api
from compass.db import connect, index_note
from compass.main import app
from compass.notes import _save_tags

Doc = dict[str, Any]


def seed(rows: list[tuple[str, str, list[str], str]]) -> None:
    """Insert notes straight into the current database (title, body, tags, created_at)."""
    conn = connect()
    with conn:
        for title, body, tags, created_at in rows:
            cur = conn.execute(
                "INSERT INTO notes(title, body, created_at) VALUES (?, ?, ?)",
                (title, body, created_at),
            )
            assert cur.lastrowid is not None
            _save_tags(conn, cur.lastrowid, tags)
            index_note(conn, cur.lastrowid, title, body, tags)
    conn.close()


def export(c: TestClient) -> Doc:
    r = c.get("/api/export")
    assert r.status_code == 200
    doc: Doc = r.json()
    return doc


def do_import(c: TestClient, doc: object) -> Any:
    return c.post(
        "/api/import",
        content=json.dumps(doc),
        headers={"content-type": "application/json"},
    )


def content(doc: Doc) -> list[tuple[Any, ...]]:
    """What an export says about each note, without ids."""
    return [(n["title"], n["body"], n["tags"], n["created_at"]) for n in doc["notes"]]


def titles(c: TestClient, q: str = "", *tags: str) -> list[str]:
    r = c.get("/api/notes", params={"q": q, "tag": list(tags)})
    return [n["title"] for n in r.json()]


SAMPLE = [
    (
        "Złożoność obliczeniowa",
        'Czas O(n) i O(log n).\nDruga linia, z przecinkiem; i "cudzysłowem" 🙂',
        ["podstawy", "teoria"],
        "2026-11-01T08:00:00+00:00",
    ),
    (
        "Indeks w bazie",
        "B-tree przyspiesza zapytania",
        ["rozmowa", "sql"],
        "2026-11-02T09:30:00+00:00",
    ),
    (
        "Metoda STAR",
        "Sytuacja, zadanie, działanie, rezultat",
        ["rozmowa", "soft skills"],
        "2026-11-03T10:15:00+00:00",
    ),
    ("Bez tagów", "", [], "2026-11-04T11:45:00+00:00"),
]


def test_round_trip_into_an_empty_database(
    authed: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seed(SAMPLE)
    original = export(authed)
    queries = [
        ("zlozonosc", ()),
        ("indkes", ()),
        ("sql", ()),
        ("rozmowa", ()),
        ("", ("rozmowa",)),
        ("nota", ()),
        ("", ()),
    ]
    before = [titles(authed, q, *t) for q, t in queries]
    tag_counts_before = authed.get("/api/tags").json()

    monkeypatch.setenv(
        "COMPASS_DB_PATH", str(tmp_path / "other" / "b.db")
    )  # a second, empty app
    assert export(authed)["notes"] == []
    r = do_import(authed, original)
    assert r.status_code == 200
    assert r.json() == {"imported": 4}

    restored = export(authed)
    assert content(restored) == content(
        original
    )  # same notes, tags, dates, newest first
    assert [titles(authed, q, *t) for q, t in queries] == before  # same search results
    assert authed.get("/api/tags").json() == tag_counts_before
    ids = [n["id"] for n in restored["notes"]]
    assert ids == sorted(ids, reverse=True)  # new ids follow creation order


def test_hand_edited_tags_are_normalised_and_creation_date_is_kept_as_written(
    authed: TestClient,
) -> None:
    doc = {
        "format": "compass-export",
        "count": 1,
        "notes": [
            {
                "title": "  Ręczna  ",
                "body": "x",
                "tags": [" SQL ", "sql", "Soft   Skills", ""],
                "created_at": "2025-01-31T23:59:58+02:00",
            }
        ],
    }
    assert do_import(authed, doc).json()["imported"] == 1
    note = export(authed)["notes"][0]
    assert (note["title"], note["tags"], note["created_at"]) == (
        "Ręczna",
        ["soft skills", "sql"],
        "2025-01-31T23:59:58+02:00",
    )
    assert titles(authed, "reczna") == [
        "Ręczna"
    ]  # indexed: found without the Polish letter


def test_notes_without_ids_and_with_naive_dates_import(authed: TestClient) -> None:
    doc = {
        "format": "compass-export",
        "count": 2,
        "notes": [
            {
                "title": "Nowsza",
                "body": "",
                "tags": [],
                "created_at": "2026-02-01T10:00:00",
            },
            {"title": "Starsza", "body": "", "tags": [], "created_at": "2026-01-01"},
        ],
    }
    assert do_import(authed, doc).json()["imported"] == 2
    assert [n["title"] for n in export(authed)["notes"]] == ["Nowsza", "Starsza"]


def test_notes_are_inserted_oldest_first_whatever_the_file_order(
    authed: TestClient,
) -> None:
    notes = [
        {"title": t, "body": "", "tags": [], "created_at": d}
        for t, d in [
            ("środek", "2026-03-02T00:00:00+00:00"),
            ("najstarsza", "2026-03-01T00:00:00+00:00"),
            ("najnowsza", "2026-03-03T00:00:00+00:00"),
        ]
    ]
    do_import(authed, {"format": "compass-export", "count": 3, "notes": notes})
    assert [n["title"] for n in export(authed)["notes"]] == [
        "najnowsza",
        "środek",
        "najstarsza",
    ]


def valid_note(**over: object) -> dict[str, object]:
    note: dict[str, object] = {
        "id": 1,
        "title": "Nota",
        "body": "treść",
        "tags": ["a"],
        "created_at": "2026-11-05T12:00:00+00:00",
    }
    note.update(over)
    return note


def doc_of(*notes: object, **over: object) -> Doc:
    doc: Doc = {
        "format": "compass-export",
        "count": len(notes),
        "notes": list(notes),
    }
    doc.update(over)
    return doc


@pytest.mark.parametrize(
    ("payload", "code", "info"),
    [
        ([], "not_an_export", {}),
        ("tekst", "not_an_export", {}),
        (
            {"format": "inny", "count": 0, "notes": []},
            "not_an_export",
            {},
        ),
        ({"count": 0, "notes": []}, "not_an_export", {}),
        ({"format": "compass-export", "count": 0}, "invalid_file", {}),
        (doc_of(notes="nie lista", count=0), "invalid_file", {}),
        (doc_of(valid_note(), count=2), "count_mismatch", {"expected": 2, "actual": 1}),
        (
            {"format": "compass-export", "notes": []},
            "count_mismatch",
            {"expected": None, "actual": 0},
        ),
        (doc_of("nie obiekt"), "invalid_note", {"index": 1, "field": "note"}),
        (doc_of(valid_note(title="")), "invalid_note", {"index": 1, "field": "title"}),
        (
            doc_of(valid_note(title="   ")),
            "invalid_note",
            {"index": 1, "field": "title"},
        ),
        (
            doc_of(valid_note(title="x" * 201)),
            "invalid_note",
            {"index": 1, "field": "title"},
        ),
        (doc_of(valid_note(title=5)), "invalid_note", {"index": 1, "field": "title"}),
        (
            doc_of(valid_note(body="x" * 20001)),
            "invalid_note",
            {"index": 1, "field": "body"},
        ),
        (doc_of(valid_note(body=None)), "invalid_note", {"index": 1, "field": "body"}),
        (
            doc_of(valid_note(tags=[f"t{i}" for i in range(11)])),
            "invalid_note",
            {"index": 1, "field": "tags"},
        ),
        (
            doc_of(valid_note(tags=["x" * 31])),
            "invalid_note",
            {"index": 1, "field": "tags"},
        ),
        (
            doc_of(valid_note(tags=["a,b"])),
            "invalid_note",
            {"index": 1, "field": "tags"},
        ),
        (doc_of(valid_note(tags="a")), "invalid_note", {"index": 1, "field": "tags"}),
        (doc_of(valid_note(tags=[1])), "invalid_note", {"index": 1, "field": "tags"}),
        (
            doc_of(valid_note(created_at="wczoraj")),
            "invalid_note",
            {"index": 1, "field": "created_at"},
        ),
        (
            doc_of(valid_note(created_at=None)),
            "invalid_note",
            {"index": 1, "field": "created_at"},
        ),
        (
            doc_of(valid_note(), valid_note(title="Druga"), valid_note(title="")),
            "invalid_note",
            {"index": 3, "field": "title"},
        ),
    ],
)
def test_invalid_files_are_rejected_with_a_code(
    authed: TestClient, payload: object, code: str, info: dict[str, object]
) -> None:
    r = do_import(authed, payload)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == code
    for key, value in info.items():
        assert detail[key] == value


def test_a_bad_note_stops_the_whole_import(authed: TestClient) -> None:
    good = [valid_note(title=f"dobra {i}") for i in range(3)]
    assert do_import(authed, doc_of(*good, valid_note(title=""))).status_code == 422
    assert export(authed)["notes"] == []  # nothing from the valid notes before it


@pytest.mark.parametrize(
    "body",
    [b"to nie json", b"", b"{", "zażółć".encode("latin-1", "ignore"), b"[" * 100000],
)
def test_body_that_is_not_json_is_rejected(authed: TestClient, body: bytes) -> None:
    r = authed.post(
        "/api/import", content=body, headers={"content-type": "application/json"}
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "not_json"


def test_oversized_upload_is_refused(
    authed: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api, "MAX_IMPORT_BYTES", 100)
    r = do_import(authed, doc_of(*[valid_note(title=f"nota {i}") for i in range(20)]))
    assert r.status_code == 413
    assert r.json()["detail"]["code"] == "file_too_large"
    assert export(authed)["notes"] == []


def test_import_requires_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        r = anon.post(
            "/api/import",
            content=json.dumps(doc_of()),
            headers={"content-type": "application/json"},
        )
    assert r.status_code == 401


def test_an_empty_export_imports_as_nothing(authed: TestClient) -> None:
    assert do_import(authed, doc_of()).json() == {"imported": 0}


def test_importing_5000_notes_is_fast(authed: TestClient) -> None:
    rows = [
        valid_note(
            title=f"Nota {i} temat{i % 50}",
            body=f"lorem ipsum dolor {i}",
            tags=[f"tag{i % 7}"],
            created_at=f"2026-01-01T00:{i // 60 % 60:02d}:{i % 60:02d}+00:00",
        )
        for i in range(5000)
    ]
    start = time.perf_counter()
    r = do_import(authed, doc_of(*rows))
    elapsed = time.perf_counter() - start
    assert r.json()["imported"] == 5000
    assert elapsed < 5.0, (
        f"import took {elapsed:.2f}s"
    )  # generous: real cost is a second or two
    assert titles(authed, "temat7")  # and the search index is filled


def add_in(c: TestClient, title: str, category: str | None) -> None:
    cid = None
    if category:
        r = c.post("/api/categories", json={"name": category})
        cid = r.json()["id"] if r.status_code == 201 else r.json()["detail"]["id"]
    r = c.post("/api/notes", json={"title": title, "category_id": cid})
    assert r.status_code == 201


def test_export_lists_category_names_and_null_for_the_default(
    authed: TestClient,
) -> None:
    add_in(authed, "a", "Dom")
    add_in(authed, "b", None)
    authed.post("/api/categories", json={"name": "Pusta"})
    doc = export(authed)
    assert {n["title"]: n["category"] for n in doc["notes"]} == {"a": "Dom", "b": None}
    assert doc["categories"] == [
        "Dom",
        "Pusta",
    ]  # a category without notes is exported too


def test_round_trip_reproduces_categories_and_counts(
    authed: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_in(authed, "a", "Dom")
    add_in(authed, "b", "Dom")
    add_in(authed, "c", None)
    doc = export(authed)
    monkeypatch.setenv("COMPASS_DB_PATH", str(tmp_path / "fresh.db"))
    with TestClient(app, follow_redirects=False) as fresh:
        assert (
            fresh.post("/login", data={"password": "test-password"}).status_code == 303
        )
        assert do_import(fresh, doc).json()["imported"] == 3
        counts = {c["name"]: c["count"] for c in fresh.get("/api/categories").json()}
        assert counts == {"Dom": 2, "": 1}
        assert export(fresh)["notes"][0]["category"] is None


def test_old_file_with_version_and_no_categories_goes_to_the_default(
    authed: TestClient,
) -> None:
    doc = doc_of(valid_note(), version=1)
    assert do_import(authed, doc).json()["imported"] == 1
    assert export(authed)["notes"][0]["category"] is None


def test_unknown_category_is_created_and_default_labels_map_to_the_default(
    authed: TestClient,
) -> None:
    doc = doc_of(
        valid_note(title="x", category="  Nowa   kategoria "),
        valid_note(title="y", category="Uncategorized"),
        valid_note(title="z", category="bez kategorii"),
    )
    assert do_import(authed, doc).status_code == 200
    got = {n["title"]: n["category"] for n in export(authed)["notes"]}
    assert got == {"x": "Nowa kategoria", "y": None, "z": None}


@pytest.mark.parametrize("bad", [5, ["Dom"], "x" * 41])
def test_bad_category_is_rejected_with_the_field(
    authed: TestClient, bad: object
) -> None:
    r = do_import(authed, doc_of(valid_note(category=bad)))
    assert r.status_code == 422
    assert r.json()["detail"] == {
        "code": "invalid_note",
        "index": 1,
        "field": "category",
    }
    assert export(authed)["count"] == 0


def test_import_replaces_everything_one_to_one(authed: TestClient) -> None:
    seed(SAMPLE)
    add_in(authed, "Stara", "Stara kategoria")
    authed.post("/api/categories", json={"name": "Pusta stara"})
    doc = doc_of(
        valid_note(title="Nowa", tags=["x"], category="Nowa kat"),
        categories=["Nowa kat", "Pusta nowa"],
    )
    assert do_import(authed, doc).json() == {"imported": 1}
    after = export(authed)
    assert [n["title"] for n in after["notes"]] == [
        "Nowa"
    ]  # nothing of the old data is left
    assert after["categories"] == ["Nowa kat", "Pusta nowa"]
    assert [t["name"] for t in authed.get("/api/tags").json()] == ["x"]
    names = [c["name"] for c in authed.get("/api/categories").json()]
    assert names == ["Nowa kat", "Pusta nowa", ""]


def test_importing_the_same_file_again_gives_the_same_state_not_duplicates(
    authed: TestClient,
) -> None:
    seed(SAMPLE)
    add_in(authed, "z kategorią", "Dom")
    doc = export(authed)
    assert do_import(authed, doc).json() == {"imported": 5}
    assert do_import(authed, doc).json() == {"imported": 5}
    again = export(authed)
    assert content(again) == content(doc) and again["categories"] == doc["categories"]


def test_identical_notes_in_a_file_are_all_kept(authed: TestClient) -> None:
    twin = valid_note(title="Bliźniak")
    assert do_import(authed, doc_of(twin, twin)).json() == {"imported": 2}
    assert export(authed)["count"] == 2


def test_a_failed_import_leaves_the_old_data(authed: TestClient) -> None:
    seed(SAMPLE)
    before = export(authed)
    r = do_import(authed, doc_of(valid_note(), valid_note(title="")))
    assert r.status_code == 422
    assert export(authed) == {
        **before,
        "exported_at": export(authed)["exported_at"],
    } or (content(export(authed)) == content(before))
    assert content(export(authed)) == content(before)


def test_export_lists_categories_without_notes(authed: TestClient) -> None:
    authed.post("/api/categories", json={"name": "Pusta"})
    add_in(authed, "a", "Dom")
    assert export(authed)["categories"] == ["Dom", "Pusta"]


@pytest.mark.parametrize("bad", ["Dom", [5], ["x" * 41], [""]])
def test_a_bad_categories_list_is_rejected(authed: TestClient, bad: object) -> None:
    r = do_import(authed, doc_of(categories=bad))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_file"
