# ruff: noqa: F811
from fastapi.testclient import TestClient

from tests.ai.test_chunks import ready
from tests.ai.test_translate import Fake, fake, setup_ai  # noqa: F401


def note(c: TestClient, title: str, body: str) -> int:
    r = c.post("/api/notes", json={"title": title, "body": body, "tags": []})
    note_id: int = r.json()["id"]
    return note_id


def related(c: TestClient, note_id: int) -> list[str]:
    r = c.get(f"/api/notes/{note_id}/related")
    assert r.status_code == 200
    return [n["title"] for n in r.json()]


def test_related_notes_are_the_closest_in_meaning_and_never_the_note_itself(
    authed: TestClient, fake: Fake
) -> None:
    ready(authed, fake)
    cats = note(authed, "Cats", "cat cat cat")
    note(authed, "Kittens", "cat cat")
    note(authed, "Dogs", "dog dog dog")
    note(authed, "Birds", "bird bird")
    authed.post("/api/ai/index")
    found = related(authed, cats)
    assert found[0] == "Kittens"
    assert "Cats" not in found and len(found) == 3


def test_related_makes_no_model_call(authed: TestClient, fake: Fake) -> None:
    ready(authed, fake)
    a = note(authed, "A", "cat")
    note(authed, "B", "cat dog")
    authed.post("/api/ai/index")
    sent = len(fake.requests)
    assert related(authed, a) == ["B"]
    assert len(fake.requests) == sent


def test_related_is_empty_until_the_note_is_indexed_and_after_it_is_edited(
    authed: TestClient, fake: Fake
) -> None:
    ready(authed, fake)
    a = note(authed, "A", "cat")
    note(authed, "B", "cat")
    assert related(authed, a) == []  # not indexed yet
    authed.post("/api/ai/index")
    assert related(authed, a) == ["B"]
    authed.put(f"/api/notes/{a}", json={"title": "A", "body": "dog", "tags": []})
    assert related(authed, a) == []  # indexed text is out of date


def test_related_is_empty_without_an_embedding_model_or_for_an_unknown_note(
    authed: TestClient, fake: Fake
) -> None:
    a = note(authed, "A", "cat")
    assert related(authed, a) == []  # AI is off: no embedding model
    ready(authed, fake)
    assert related(authed, 9999) == []
