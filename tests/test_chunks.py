# ruff: noqa: F811
import json

from fastapi.testclient import TestClient

from compass import chunks
from compass.db import connect
from tests.test_translate import Fake, add, fake, setup_ai  # noqa: F401

WORDS = ("cat", "dog", "bird")


def embedder(texts: list[str]) -> list[list[float]]:
    """A vector of keyword counts (plus 1, so none is empty): similar words = similar direction."""
    return [[t.lower().count(w) + 0.01 for w in WORDS] for t in texts]


def ready(c: TestClient, f: Fake) -> dict[str, object]:
    f.embedder = embedder
    setup_ai(c, f, ai_embed_model_local="emb")
    return {
        "ai_enabled": True,
        "ai_connection": "local",
        "ai_address": f.url,
        "ai_model_local": "m1",
        "ai_embed_model_local": "emb",
        "ai_vision_model_local": "",
    }


def events(response: object) -> list[dict[str, object]]:
    return [json.loads(line) for line in response.text.splitlines()]  # type: ignore[attr-defined]


def count() -> int:
    conn = connect()
    try:
        return int(conn.execute("SELECT COUNT(*) FROM note_chunks").fetchone()[0])
    finally:
        conn.close()


def test_a_note_is_cut_at_headings_and_every_chunk_carries_the_title() -> None:
    body = "intro\n\n# One\ntext one\n\n## Two\ntext two"
    assert chunks.split("T", body) == [
        "T\n\nintro",
        "T\n\n# One\ntext one",
        "T\n\n## Two\ntext two",
    ]


def test_a_hash_in_a_code_block_is_not_a_heading() -> None:
    body = "# A\n```py\n# comment\nx = 1\n```"
    assert chunks.split("T", body) == [f"T\n\n{body}"]


def test_long_text_is_cut_to_the_size_limit_and_nothing_is_lost() -> None:
    paragraphs = [f"p{i} " + "x" * 500 for i in range(5)]
    out = chunks.split("T", "\n\n".join(paragraphs))
    assert len(out) > 1 and all(len(c) <= chunks.CHUNK_CHARS + 10 for c in out)
    assert all(p in "\n".join(out) for p in paragraphs)
    one = chunks.split("T", "y" * 3000)
    assert "".join(c.removeprefix("T\n\n") for c in one) == "y" * 3000


def test_an_empty_body_is_the_title_alone() -> None:
    assert chunks.split("Only title", "") == ["Only title"]


def test_status_is_zero_without_an_embedding_model(authed: TestClient) -> None:
    add(authed)
    r = authed.get("/api/ai/index")
    assert r.json() == {"total": 1, "indexed": 0}


def test_index_embeds_new_notes_and_then_has_nothing_to_do(
    authed: TestClient, fake: Fake
) -> None:
    ready(authed, fake)
    add(authed, "a cat")
    add(authed, "a dog")
    r = authed.post("/api/ai/index")
    assert r.status_code == 200
    got = events(r)
    assert got[0] == {"type": "start", "total": 2}
    assert got[-1] == {"type": "done"} and got[-2]["done"] == 2
    assert authed.get("/api/ai/index").json() == {"total": 2, "indexed": 2}
    sent = len(fake.requests)
    assert events(authed.post("/api/ai/index"))[0] == {"type": "start", "total": 0}
    assert len(fake.requests) == sent  # nothing stale, no model call


def test_an_edited_note_is_stale_and_reindexed(authed: TestClient, fake: Fake) -> None:
    ready(authed, fake)
    nid = add(authed, "a cat")
    authed.post("/api/ai/index")
    authed.put(f"/api/notes/{nid}", json={"title": "T", "body": "a dog", "tags": []})
    assert authed.get("/api/ai/index").json() == {"total": 1, "indexed": 0}
    authed.post("/api/ai/index")
    assert authed.get("/api/ai/index").json() == {"total": 1, "indexed": 1}
    conn = connect()
    try:
        (text,) = conn.execute("SELECT text FROM note_chunks").fetchone()
    finally:
        conn.close()
    assert "dog" in text


def test_a_changed_embedding_model_reindexes(authed: TestClient, fake: Fake) -> None:
    ready(authed, fake)
    add(authed)
    authed.post("/api/ai/index")
    authed.put("/api/settings", json={"ai_embed_model_local": "other"})
    assert authed.get("/api/ai/index").json()["indexed"] == 0
    assert events(authed.post("/api/ai/index"))[0]["total"] == 1


def test_deleting_a_note_removes_its_chunks(authed: TestClient, fake: Fake) -> None:
    ready(authed, fake)
    nid = add(authed)
    authed.post("/api/ai/index")
    assert count() > 0
    authed.delete(f"/api/notes/{nid}")
    assert count() == 0


def test_search_ranks_by_meaning_and_ignores_other_models(
    authed: TestClient, fake: Fake
) -> None:
    s = ready(authed, fake)
    add(authed, "cat cat cat")
    add(authed, "dog dog")
    authed.post("/api/ai/index")
    top = chunks.search(s, embedder(["cat"])[0], 5)
    assert [c[2].count("cat") for c in top] == [3, 0]
    assert top[0][3] > top[1][3]
    assert chunks.search({**s, "ai_embed_model_local": "other"}, [1.0, 0, 0], 5) == []


def test_provider_failure_keeps_what_is_written(authed: TestClient, fake: Fake) -> None:
    ready(authed, fake)
    add(authed, "a cat")
    add(authed, "a dog")
    first = {"n": 0}

    def flaky(texts: list[str]) -> list[list[float]]:
        first["n"] += 1
        if first["n"] > 1:
            raise RuntimeError
        return embedder(texts)

    fake.embedder = flaky
    got = events(authed.post("/api/ai/index"))
    assert got[1]["type"] == "progress" and got[-1]["type"] == "error"
    assert authed.get("/api/ai/index").json() == {"total": 2, "indexed": 1}


def test_index_is_refused_before_streaming(authed: TestClient, fake: Fake) -> None:
    add(authed)
    assert authed.post("/api/ai/index").status_code == 409  # AI off
    setup_ai(authed, fake)  # on, but no embedding model
    r = authed.post("/api/ai/index")
    assert r.status_code == 409 and r.json()["detail"] == {"code": "not_configured"}
    assert fake.requests == []


def test_index_needs_a_login() -> None:
    from compass.main import app

    c = TestClient(app, follow_redirects=False)
    assert c.get("/api/ai/index").status_code == 401
    assert c.post("/api/ai/index").status_code == 401


def test_the_export_does_not_carry_the_index(authed: TestClient, fake: Fake) -> None:
    ready(authed, fake)
    add(authed)
    authed.post("/api/ai/index")
    assert "emb" not in authed.get("/api/export").text
    assert "vec" not in authed.get("/api/export").text


def test_the_search_index_is_untouched(authed: TestClient, fake: Fake) -> None:
    ready(authed, fake)
    add(authed, "cat")
    conn = connect()
    before = conn.execute("SELECT rowid, * FROM notes_fts").fetchall()
    conn.close()
    authed.post("/api/ai/index")
    conn = connect()
    assert conn.execute("SELECT rowid, * FROM notes_fts").fetchall() == before
    conn.close()


def test_the_index_can_be_cleared_and_is_rebuilt_on_demand(
    authed: TestClient, fake: Fake
) -> None:
    ready(authed, fake)
    nid = add(authed, "a cat")
    authed.post("/api/ai/index")
    assert count() > 0
    assert authed.delete("/api/ai/index").status_code == 204
    assert count() == 0
    assert authed.get("/api/ai/index").json() == {"total": 1, "indexed": 0}
    assert authed.get(f"/api/notes/{nid}").status_code == 200  # the note is untouched
    assert authed.delete("/api/ai/index").status_code == 204  # clearing nothing is fine
    authed.post("/api/ai/index")
    assert authed.get("/api/ai/index").json() == {"total": 1, "indexed": 1}


def test_clearing_the_index_needs_a_login() -> None:
    from compass.main import app

    assert TestClient(app).delete("/api/ai/index").status_code == 401
