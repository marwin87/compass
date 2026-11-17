import json
import re
import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from compass.db import connect
from compass.main import app


def add(
    c: TestClient, title: str, body: str = "", tags: list[str] | None = None
) -> int:
    r = c.post("/api/notes", json={"title": title, "body": body, "tags": tags or []})
    assert r.status_code == 201
    note_id: int = r.json()["id"]
    return note_id


def export(c: TestClient, **params: str) -> dict[str, object]:
    r = c.get("/api/export", params=params)
    assert r.status_code == 200
    document: dict[str, object] = json.loads(r.text)
    return document


def test_document_shape_and_constants(authed: TestClient) -> None:
    add(authed, "Indeks", "b-tree", ["sql", "teoria"])
    doc = export(authed)
    assert list(doc) == ["format", "version", "exported_at", "count", "notes"]
    assert doc["format"] == "compass-export"
    assert doc["version"] == 1
    assert doc["count"] == 1 == len(doc["notes"])  # type: ignore[arg-type]
    exported_at = datetime.fromisoformat(str(doc["exported_at"]))
    assert exported_at.tzinfo is not None
    assert abs((datetime.now(UTC) - exported_at).total_seconds()) < 60
    note = doc["notes"][0]  # type: ignore[index]
    assert list(note) == ["id", "title", "body", "tags", "created_at"]
    assert note["tags"] == ["sql", "teoria"]


def test_each_note_matches_the_api(authed: TestClient) -> None:
    ids = [add(authed, f"n{i}", f"b{i}", ["a", "z"]) for i in range(3)]
    exported = {n["id"]: n for n in export(authed)["notes"]}  # type: ignore[attr-defined]
    for note_id in ids:
        assert exported[note_id] == authed.get(f"/api/notes/{note_id}").json()


def test_every_note_is_exported_not_just_the_first_fifty(authed: TestClient) -> None:
    for i in range(120):
        add(authed, f"nota {i}")
    doc = export(authed)
    assert doc["count"] == 120 and len(doc["notes"]) == 120  # type: ignore[arg-type]


def test_newest_first(authed: TestClient) -> None:
    first, second, third = (add(authed, t) for t in ("pierwsza", "druga", "trzecia"))
    ids = [n["id"] for n in export(authed)["notes"]]  # type: ignore[attr-defined]
    assert ids == [third, second, first]


def test_tags_are_alphabetical_and_empty_when_there_are_none(
    authed: TestClient,
) -> None:
    add(authed, "z tagami", tags=["zeta", "alfa", "soft skills"])
    add(authed, "bez tagów")
    notes = {n["title"]: n["tags"] for n in export(authed)["notes"]}  # type: ignore[attr-defined]
    assert notes == {"z tagami": ["alfa", "soft skills", "zeta"], "bez tagów": []}


def test_empty_database_gives_a_valid_empty_file(authed: TestClient) -> None:
    doc = export(authed)
    assert doc["notes"] == [] and doc["count"] == 0
    assert doc["format"] == "compass-export" and doc["version"] == 1


def test_text_survives_unchanged_and_is_not_escaped(authed: TestClient) -> None:
    title = 'Złożoność "O(n)", zażółć gęślą jaźń'
    body = "linia 1\nlinia 2\n\tz tabulatorem, przecinkami; i </script><b>html</b> 🙂\\ukośnik"
    add(authed, title, body, ["wydajność", "ąę ść"])
    r = authed.get("/api/export")
    note = json.loads(r.text)["notes"][0]
    assert (note["title"], note["body"], note["tags"]) == (
        title,
        body,
        ["wydajność", "ąę ść"],
    )
    assert (
        "Złożoność" in r.text and "zażółć gęślą jaźń" in r.text
    )  # real letters, not \u escapes
    assert "\\u0142" not in r.text
    assert r.content.decode("utf-8") == r.text  # the file is valid UTF-8


def test_search_and_tag_filters_do_not_apply(authed: TestClient) -> None:
    add(authed, "Indeks", tags=["sql"])
    add(authed, "Fotosynteza", tags=["nauka"])
    assert export(authed, q="indeks")["count"] == 2
    assert export(authed, tag="sql")["count"] == 2
    assert export(authed, q="zzz", tag="nie ma")["count"] == 2


def test_download_headers(authed: TestClient) -> None:
    before = datetime.now(UTC).date().isoformat()
    r = authed.get("/api/export")
    after = datetime.now(UTC).date().isoformat()
    match = re.fullmatch(
        r'attachment; filename="compass-export-(\d{4}-\d{2}-\d{2})\.json"',
        r.headers["content-disposition"],
    )
    assert match and match.group(1) in {before, after}
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["content-type"].startswith("application/json")


def test_export_does_not_change_the_database(authed: TestClient) -> None:
    add(authed, "Indeks", "b-tree", ["sql"])

    def snapshot() -> list[tuple[object, ...]]:
        conn = connect()
        rows = (
            conn.execute("SELECT * FROM notes").fetchall()
            + conn.execute("SELECT * FROM note_tags").fetchall()
        )
        conn.close()
        return rows

    before = snapshot()
    export(authed)
    assert snapshot() == before


def test_export_requires_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        r = anon.get("/api/export")
    assert r.status_code == 401
    assert "notes" not in r.text


def test_exporting_5000_notes_is_fast(authed: TestClient) -> None:
    conn = connect()
    with conn:
        conn.executemany(
            "INSERT INTO tags(name) VALUES (?)", [(f"tag{i}",) for i in range(7)]
        )
        for i in range(5000):
            cur = conn.execute(
                "INSERT INTO notes(title, body, created_at) VALUES (?, ?, 'x')",
                (f"Nota {i}", f"lorem ipsum dolor {i} " * 5),
            )
            conn.execute(
                "INSERT INTO note_tags(note_id, tag_id) SELECT ?, id FROM tags WHERE name = ?",
                (cur.lastrowid, f"tag{i % 7}"),
            )
    conn.close()
    start = time.perf_counter()
    doc = export(authed)
    elapsed = time.perf_counter() - start
    assert doc["count"] == 5000
    assert elapsed < 1.0, (
        f"export took {elapsed:.2f}s"
    )  # generous: real cost is a fraction of this
