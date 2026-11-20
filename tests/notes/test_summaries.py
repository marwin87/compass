# ruff: noqa: F811  (the `fake` fixture is imported from test_translate)
import json
from typing import Any

from fastapi.testclient import TestClient

from compass.db import connect
from compass.notes import summaries
from tests.ai.test_translate import (
    Fake,
    add,
    fake,  # noqa: F401  (the fixture, for pytest)
    setup_ai,
)

TEXT = "## Summary\n\nShort.\n\n## Key points\n\n- one"


def summarize(c: TestClient, nid: int) -> Any:
    r = c.post(f"/api/notes/{nid}/summarize")
    assert r.status_code == 200
    return r.json()


def stored() -> list[tuple[Any, ...]]:
    conn = connect()
    try:
        return [tuple(r) for r in conn.execute("SELECT * FROM note_summaries")]
    finally:
        conn.close()


def test_a_summary_is_kept_and_read_back(authed: TestClient, fake: Fake) -> None:
    setup_ai(authed, fake)
    fake.reply = TEXT
    nid = add(authed, "Docker runs containers.")
    assert authed.get(f"/api/notes/{nid}/summary").json() is None  # none yet
    made = summarize(authed, nid)
    again = authed.get(f"/api/notes/{nid}/summary").json()
    assert again == made and again["text"] == TEXT and again["stale"] is False


def test_it_goes_stale_when_the_note_is_edited_and_a_new_one_replaces_it(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    fake.reply = TEXT
    nid = add(authed, "Docker runs containers.")
    summarize(authed, nid)
    authed.put(f"/api/notes/{nid}", json={"title": "T", "body": "New text", "tags": []})
    old = authed.get(f"/api/notes/{nid}/summary").json()
    assert old["text"] == TEXT and old["stale"] is True  # still shown, but flagged
    fake.reply = "## Summary\n\nFresh."
    summarize(authed, nid)
    fresh = authed.get(f"/api/notes/{nid}/summary").json()
    assert fresh["text"] == "## Summary\n\nFresh." and fresh["stale"] is False
    assert len(stored()) == 1  # replaced, not added


def test_an_edit_made_while_the_model_works_leaves_the_summary_stale(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    nid = add(authed, "old text")
    old = summaries.digest("T", "old text")  # what was sent to the model
    authed.put(f"/api/notes/{nid}", json={"title": "T", "body": "new", "tags": []})
    assert summaries.save(nid, "summary of the old text", old) is not None
    assert authed.get(f"/api/notes/{nid}/summary").json()["stale"] is True


def test_a_failed_summary_keeps_nothing_and_leaves_the_old_one(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    fake.reply = TEXT
    nid = add(authed)
    summarize(authed, nid)
    fake.status = 500
    assert authed.post(f"/api/notes/{nid}/summarize").status_code == 502
    assert authed.get(f"/api/notes/{nid}/summary").json()["text"] == TEXT


def test_delete_summary_is_idempotent_and_leaves_the_note(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    nid = add(authed)
    summarize(authed, nid)
    assert authed.delete(f"/api/notes/{nid}/summary").status_code == 204
    assert authed.delete(f"/api/notes/{nid}/summary").status_code == 204
    assert authed.get(f"/api/notes/{nid}/summary").json() is None
    assert authed.get(f"/api/notes/{nid}").status_code == 200


def test_it_goes_with_the_note_and_with_clear_all(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    a, b = add(authed), add(authed)
    summarize(authed, a)
    summarize(authed, b)
    authed.delete(f"/api/notes/{a}")
    assert len(stored()) == 2  # the summary stays with the note in the Trash
    assert authed.delete(f"/api/trash/{a}").status_code == 204
    assert len(stored()) == 1  # cascaded with the note once it is deleted for good
    assert authed.delete("/api/data").status_code == 204
    assert stored() == []


def test_export_carries_summaries_only_for_notes_that_have_one(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    fake.reply = TEXT
    with_one, without = add(authed), add(authed)
    summarize(authed, with_one)
    notes = authed.get("/api/export").json()["notes"]
    by_id = {n["id"]: n for n in notes}
    assert by_id[with_one]["summary"]["text"] == TEXT
    assert by_id[with_one]["summary"]["stale"] is False
    assert "summary" not in by_id[without]  # a file without summaries stays as it was


def test_import_restores_summaries_and_their_staleness(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    fake.reply = TEXT
    fresh_id, stale_id = add(authed, "fresh"), add(authed, "will change")
    summarize(authed, fresh_id)
    summarize(authed, stale_id)
    authed.put(
        f"/api/notes/{stale_id}", json={"title": "T", "body": "changed", "tags": []}
    )
    backup = authed.get("/api/export").text
    authed.delete("/api/data")  # lose everything
    assert authed.post("/api/import", content=backup).status_code == 200
    got = {
        n["body"]: authed.get(f"/api/notes/{n['id']}/summary").json()
        for n in authed.get("/api/notes").json()
    }
    assert got["fresh"]["text"] == TEXT and got["fresh"]["stale"] is False
    assert got["changed"]["text"] == TEXT and got["changed"]["stale"] is True


def test_a_file_without_summaries_still_imports_and_a_bad_summary_is_refused(
    authed: TestClient,
) -> None:
    def doc(summary: object) -> str:
        note: dict[str, object] = {
            "title": "A",
            "body": "x",
            "tags": [],
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        if summary is not None:
            note["summary"] = summary
        return json.dumps({"format": "compass-export", "count": 1, "notes": [note]})

    assert authed.post("/api/import", content=doc(None)).status_code == 200
    for bad in (
        "text",
        {"text": "", "created_at": "2026-01-01T00:00:00+00:00", "stale": False},
        {"text": "s", "created_at": "not a date", "stale": False},
        {"text": "s", "created_at": "2026-01-01T00:00:00+00:00"},
    ):
        r = authed.post("/api/import", content=doc(bad))
        assert r.status_code == 422, bad
        assert r.json()["detail"] == {
            "code": "invalid_note",
            "index": 1,
            "field": "summary",
        }
    assert (
        len(authed.get("/api/notes").json()) == 1
    )  # the failed imports changed nothing
