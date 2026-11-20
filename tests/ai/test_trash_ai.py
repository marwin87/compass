# ruff: noqa: F811
import json

from fastapi.testclient import TestClient

from compass.db import connect
from tests.ai.test_ask import note
from tests.ai.test_chat import new, put
from tests.ai.test_chunks import events, ready
from tests.ai.test_translate import Fake, fake, setup_ai  # noqa: F401


def indexed_notes() -> set[int]:
    conn = connect()
    try:
        return {r[0] for r in conn.execute("SELECT DISTINCT note_id FROM note_chunks")}
    finally:
        conn.close()


def cited(got: list[dict[str, object]]) -> list[int]:
    """The ids of the notes whose excerpts the chat found (the `excerpts` event, if any)."""
    found: list[int] = []
    for e in got:
        if e["type"] == "excerpts":
            rows = e["excerpts"]
            assert isinstance(rows, list)
            found += [x["id"] for x in rows]
    return found


def related(c: TestClient, note_id: int) -> list[str]:
    return [n["title"] for n in c.get(f"/api/notes/{note_id}/related").json()]


def test_the_chat_neither_searches_nor_cites_a_note_in_the_trash(
    authed: TestClient, fake: Fake
) -> None:
    ready(authed, fake)
    kotki = note(authed, "Kotki", "cat cat cat lubi mleko")
    note(authed, "Psy", "dog dog szczeka")
    authed.post("/api/ai/index")
    fake.sse = ["Mleko [1]."]
    cid = new(authed)
    before = put(authed, cid, "co lubi cat?")
    assert kotki in cited(before)  # control: it is found
    authed.delete(f"/api/notes/{kotki}")
    fake.sse = ["Nic."]
    after = put(authed, cid, "co lubi cat?")
    assert "Kotki" not in json.dumps(
        fake.requests[-1]["body"]
    )  # nothing of it is sent to the model
    assert kotki not in cited(after)


def test_a_note_in_the_trash_is_never_embedded_or_counted(
    authed: TestClient, fake: Fake
) -> None:
    ready(authed, fake)
    gone, kept = note(authed, "Gone", "cat"), note(authed, "Kept", "dog")
    authed.delete(f"/api/notes/{gone}")
    assert authed.get("/api/ai/index").json() == {"total": 1, "indexed": 0}
    got = events(authed.post("/api/ai/index"))
    assert got[0] == {"type": "start", "total": 1} and got[-1] == {"type": "done"}
    assert indexed_notes() == {kept}


def test_trashing_a_note_drops_its_vectors(authed: TestClient, fake: Fake) -> None:
    ready(authed, fake)
    a = note(authed, "A", "cat")
    authed.post("/api/ai/index")
    assert indexed_notes() == {a}
    authed.delete(f"/api/notes/{a}")
    assert indexed_notes() == set()


def test_related_notes_ignore_the_trash_both_ways(
    authed: TestClient, fake: Fake
) -> None:
    ready(authed, fake)
    a = note(authed, "Cats", "cat cat")
    b = note(authed, "Kittens", "cat cat")
    c = note(authed, "Birds", "bird bird")
    authed.post("/api/ai/index")
    assert related(authed, a) == ["Kittens", "Birds"]  # control
    authed.delete(f"/api/notes/{b}")
    assert related(authed, a) == ["Birds"]  # a note in the Trash is not suggested
    assert related(authed, b) == []  # and has no related notes itself
    assert c


def test_a_restored_note_is_searchable_at_once_but_counts_as_not_indexed_until_the_next_run(
    authed: TestClient, fake: Fake
) -> None:
    ready(authed, fake)
    a = note(authed, "Cats", "cat cat")
    b = note(authed, "Kittens", "cat cat")
    authed.post("/api/ai/index")
    authed.delete(f"/api/notes/{b}")
    assert authed.post(f"/api/trash/{b}/restore").status_code == 200
    assert authed.get("/api/ai/index").json() == {"total": 2, "indexed": 1}
    assert related(authed, b) == []  # no vectors yet: the section stays hidden
    got = events(authed.post("/api/ai/index"))
    assert got[0] == {"type": "start", "total": 1}  # no model call before this
    assert related(authed, b) == ["Cats"] and related(authed, a) == ["Kittens"]


def test_a_source_in_the_trash_shows_as_deleted_and_links_again_once_restored(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    nid = note(authed, "Kotki", "Kot lubi mleko")
    fake.sse = ["Mleko [1]."]
    cid = new(authed)
    put(authed, cid, "co lubi kot?")

    def source() -> dict[str, object]:
        thread = authed.get(f"/api/chats/{cid}").json()
        source: dict[str, object] = thread["messages"][1]["sources"][0]
        return source

    assert source() == {"id": nid, "title": "Kotki", "deleted": False}
    authed.delete(f"/api/notes/{nid}")
    assert source() == {"id": nid, "title": "Kotki", "deleted": True}
    authed.post(f"/api/trash/{nid}/restore")
    assert source() == {"id": nid, "title": "Kotki", "deleted": False}
