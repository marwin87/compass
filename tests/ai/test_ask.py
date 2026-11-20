# ruff: noqa: F811
import pytest
from fastapi.testclient import TestClient

from compass import ai
from compass.ai import chunks, retrieval
from compass.db import connect
from tests.ai.test_chunks import embedder, ready
from tests.ai.test_translate import Fake, fake, setup_ai  # noqa: F401


def note(c: TestClient, title: str, body: str) -> int:
    r = c.post("/api/notes", json={"title": title, "body": body, "tags": []})
    assert r.status_code == 201
    return int(r.json()["id"])


def titles(found: list[retrieval.Excerpt]) -> list[str]:
    return [e.title for e in found]


def test_keyword_retrieval_works_without_an_embedding_model(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    note(authed, "Kotki", "Kot lubi mleko")
    note(authed, "Psy", "Pies szczeka")
    from compass import settings

    found = retrieval.retrieve(settings.current(), "co lubi kot?")
    assert titles(found) == ["Kotki"]
    assert fake.requests == []  # no model call at all


def test_vector_hits_rank_by_meaning_and_merge_with_keywords(
    authed: TestClient, fake: Fake
) -> None:
    s = ready(authed, fake)
    note(authed, "Cats", "cat cat cat")
    note(authed, "Dogs", "dog dog")
    note(authed, "Mix", "word bird")
    authed.post("/api/ai/index")
    found = retrieval.retrieve(s, "tell me about the cat")
    assert titles(found)[0] == "Cats"
    assert {e.note_id for e in found} >= {1}
    assert fake.requests[-1]["path"] == "/embeddings"  # the question was embedded


def test_a_follow_up_uses_the_previous_question(authed: TestClient, fake: Fake) -> None:
    s = ready(authed, fake)
    note(authed, "Cats", "cat cat cat")
    authed.post("/api/ai/index")
    found = retrieval.retrieve(s, "and when?", ["tell me about the cat"])
    assert titles(found) == ["Cats"]
    assert "cat" in fake.requests[-1]["body"]["input"][0]


def test_at_most_two_chunks_per_note_and_eight_notes(
    authed: TestClient, fake: Fake
) -> None:
    s = ready(authed, fake)
    note(authed, "Big", "\n\n".join(f"# S{i}\ncat {i}" for i in range(5)))
    for i in range(10):
        note(authed, f"N{i}", "cat")
    authed.post("/api/ai/index")
    found = retrieval.retrieve(s, "cat")
    per = {
        n: sum(1 for e in found if e.note_id == n) for n in {e.note_id for e in found}
    }
    assert max(per.values()) <= retrieval.PER_NOTE and len(per) <= retrieval.MAX_NOTES


def test_the_character_budget_is_kept(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = ready(authed, fake)
    for i in range(5):
        note(authed, f"N{i}", "cat " * 100)
    authed.post("/api/ai/index")
    monkeypatch.setattr(retrieval, "CONTEXT_CHARS", 900)
    found = retrieval.retrieve(s, "cat")
    assert 0 < len(found) < 5 and sum(len(e.text) for e in found) <= 900


def test_noise_words_do_not_pull_in_every_note(authed: TestClient, fake: Fake) -> None:
    setup_ai(authed, fake)
    note(authed, "Kotki", "Kot lubi mleko")
    note(authed, "Inne", "w co i a o")
    from compass import settings

    assert titles(retrieval.retrieve(settings.current(), "w co i a o?")) == []


def test_nothing_found_is_an_empty_list(authed: TestClient, fake: Fake) -> None:
    s = ready(authed, fake)
    assert retrieval.retrieve(s, "anything at all") == []


def test_an_embedding_failure_is_an_ai_error(authed: TestClient, fake: Fake) -> None:
    s = ready(authed, fake)
    fake.status = 500
    with pytest.raises(ai.AIError):
        retrieval.retrieve(s, "cat")


def test_retrieval_leaves_both_indexes_untouched(
    authed: TestClient, fake: Fake
) -> None:
    s = ready(authed, fake)
    note(authed, "Cats", "cat")
    authed.post("/api/ai/index")
    conn = connect()
    fts = conn.execute("SELECT rowid, * FROM notes_fts").fetchall()
    vec = conn.execute("SELECT * FROM note_chunks").fetchall()
    conn.close()
    retrieval.retrieve(s, "cat")
    conn = connect()
    assert conn.execute("SELECT rowid, * FROM notes_fts").fetchall() == fts
    assert conn.execute("SELECT * FROM note_chunks").fetchall() == vec
    conn.close()
    assert chunks.status(s)["indexed"] == 1 and embedder(["x"])
