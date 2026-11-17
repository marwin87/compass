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
    assert r.json() == {"imported": 4, "skipped": 0, "total": 4}

    restored = export(authed)
    assert content(restored) == content(
        original
    )  # same notes, tags, dates, newest first
    assert [titles(authed, q, *t) for q, t in queries] == before  # same search results
    assert authed.get("/api/tags").json() == tag_counts_before
    ids = [n["id"] for n in restored["notes"]]
    assert ids == sorted(ids, reverse=True)  # new ids follow creation order


def test_importing_the_same_file_again_changes_nothing(authed: TestClient) -> None:
    seed(SAMPLE)
    doc = export(authed)
    r = do_import(authed, doc)  # into the app the file came from
    assert r.json() == {"imported": 0, "skipped": 4, "total": 4}
    assert content(export(authed)) == content(doc)


def test_second_import_into_another_app_is_idempotent(
    authed: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seed(SAMPLE)
    doc = export(authed)
    monkeypatch.setenv("COMPASS_DB_PATH", str(tmp_path / "b" / "b.db"))
    assert do_import(authed, doc).json()["imported"] == 4
    assert do_import(authed, doc).json() == {
        "imported": 0,
        "skipped": 4,
        "total": 4,
    }  # ids differ, content decides


def test_deleted_notes_come_back_and_the_rest_is_skipped(authed: TestClient) -> None:
    seed(SAMPLE)
    doc = export(authed)
    authed.delete(f"/api/notes/{doc['notes'][0]['id']}")
    authed.delete(f"/api/notes/{doc['notes'][2]['id']}")
    assert do_import(authed, doc).json() == {"imported": 2, "skipped": 2, "total": 4}
    assert sorted(content(export(authed))) == sorted(content(doc))


def test_identical_notes_in_a_file_are_both_kept_as_a_multiset(
    authed: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    twin = ("Bliźniak", "ta sama treść", ["a"], "2026-11-05T12:00:00+00:00")
    seed([twin, twin])
    doc = export(authed)
    assert doc["count"] == 2
    monkeypatch.setenv("COMPASS_DB_PATH", str(tmp_path / "b" / "b.db"))
    assert do_import(authed, doc).json() == {"imported": 2, "skipped": 0, "total": 2}
    assert do_import(authed, doc).json() == {"imported": 0, "skipped": 2, "total": 2}


def test_one_existing_copy_of_two_identical_notes_imports_exactly_the_other(
    authed: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    twin: tuple[str, str, list[str], str] = (
        "Bliźniak",
        "ta sama treść",
        [],
        "2026-11-05T12:00:00+00:00",
    )
    seed([twin, twin])
    doc = export(authed)
    monkeypatch.setenv("COMPASS_DB_PATH", str(tmp_path / "b" / "b.db"))
    seed([twin])
    assert do_import(authed, doc).json() == {"imported": 1, "skipped": 1, "total": 2}
    assert export(authed)["count"] == 2


def test_a_note_edited_after_export_comes_back_as_an_extra_note(
    authed: TestClient,
) -> None:
    seed(SAMPLE)
    doc = export(authed)
    first = doc["notes"][-1]
    authed.put(
        f"/api/notes/{first['id']}",
        json={
            "title": first["title"],
            "body": "poprawiona treść",
            "tags": first["tags"],
        },
    )
    assert do_import(authed, doc).json() == {"imported": 1, "skipped": 3, "total": 4}
    bodies = [
        n["body"] for n in export(authed)["notes"] if n["title"] == first["title"]
    ]
    assert sorted(bodies) == sorted([first["body"], "poprawiona treść"])


def test_tags_of_a_skipped_duplicate_stay_as_they_are(authed: TestClient) -> None:
    seed([("Nota", "treść", ["stary"], "2026-11-05T12:00:00+00:00")])
    doc = export(authed)
    doc["notes"][0]["tags"] = ["nowy", "inny"]
    assert do_import(authed, doc).json()["skipped"] == 1
    assert export(authed)["notes"][0]["tags"] == ["stary"]


def test_hand_edited_tags_are_normalised_and_creation_date_is_kept_as_written(
    authed: TestClient,
) -> None:
    doc = {
        "format": "compass-export",
        "version": 1,
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
        "version": 1,
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
    do_import(
        authed, {"format": "compass-export", "version": 1, "count": 3, "notes": notes}
    )
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
        "version": 1,
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
            {"format": "inny", "version": 1, "count": 0, "notes": []},
            "not_an_export",
            {},
        ),
        ({"version": 1, "count": 0, "notes": []}, "not_an_export", {}),
        (doc_of(version=2), "unsupported_version", {"version": 2}),
        (doc_of(version="1"), "unsupported_version", {"version": "1"}),
        (doc_of(version=True), "unsupported_version", {}),
        ({"format": "compass-export", "version": 1, "count": 0}, "invalid_file", {}),
        (doc_of(notes="nie lista", count=0), "invalid_file", {}),
        (doc_of(valid_note(), count=2), "count_mismatch", {"expected": 2, "actual": 1}),
        (
            {"format": "compass-export", "version": 1, "notes": []},
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
    assert do_import(authed, doc_of()).json() == {
        "imported": 0,
        "skipped": 0,
        "total": 0,
    }


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
