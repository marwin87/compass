# ruff: noqa: F811
import pytest
from fastapi.testclient import TestClient

from compass import ai, ask, chat
from tests.test_ask import note
from tests.test_chunks import events, ready
from tests.test_translate import Fake, fake, setup_ai  # noqa: F401


def new(c: TestClient) -> int:
    r = c.post("/api/chats")
    assert r.status_code == 201
    return int(r.json()["id"])


def put(c: TestClient, cid: int, question: str) -> list[dict[str, object]]:
    r = c.post(f"/api/chats/{cid}/ask", json={"question": question})
    assert r.status_code == 200
    return events(r)


def types(got: list[dict[str, object]]) -> list[object]:
    return [e["type"] for e in got]


def test_a_question_is_answered_from_the_notes_with_sources(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    nid = note(authed, "Kotki", "Kot lubi mleko")
    note(authed, "Psy", "Pies szczeka")
    fake.sse = ["Kot lubi ", "mleko [1]."]
    cid = new(authed)
    got = put(authed, cid, "co lubi kot?")
    assert types(got) == ["excerpts", "delta", "delta", "done"]
    assert got[0]["excerpts"] == [{"n": 1, "id": nid, "title": "Kotki"}]
    assert (
        "".join(str(e["text"]) for e in got if e["type"] == "delta")
        == "Kot lubi mleko [1]."
    )
    assert got[-1]["sources"] == [{"id": nid, "title": "Kotki", "deleted": False}]
    assert got[-1]["text"] == "Kot lubi mleko [1]."
    system, user = fake.requests[-1]["body"]["messages"]
    assert system["content"] == chat.SYSTEM
    assert (
        "[1] Kotki" in user["content"] and "Question: co lubi kot?" in user["content"]
    )
    assert "Psy" not in user["content"]  # only what the question found is sent
    thread = authed.get(f"/api/chats/{cid}").json()
    assert thread["title"] == "co lubi kot?"
    assert [m["role"] for m in thread["messages"]] == ["user", "assistant"]
    assert thread["messages"][1]["sources"][0]["id"] == nid


def test_the_next_question_sends_the_conversation_so_far(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    note(authed, "Kotki", "Kot lubi mleko")
    fake.sse = ["Mleko [1]."]
    cid = new(authed)
    put(authed, cid, "co lubi kot?")
    put(authed, cid, "a kiedy?")
    roles = [m["role"] for m in fake.requests[-1]["body"]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert fake.requests[-1]["body"]["messages"][1]["content"] == "co lubi kot?"
    assert fake.requests[-1]["body"]["messages"][2]["content"] == "Mleko [1]."


def test_only_the_last_turns_are_sent(authed: TestClient, fake: Fake) -> None:
    setup_ai(authed, fake)
    fake.sse = ["ok"]
    cid = new(authed)
    for i in range(9):
        put(authed, cid, f"question {i}")
    sent = fake.requests[-1]["body"]["messages"]
    assert len(sent) == 1 + chat.HISTORY_MESSAGES + 1
    assert sent[1]["content"] == "question 2"  # 8 earlier turns, the last 6 kept


def test_nothing_found_still_asks_the_model_to_say_so(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    fake.sse = ["Nie ma tego w notatkach."]
    got = put(authed, new(authed), "co z pogodą?")
    assert got[0]["excerpts"] == [] and got[-1]["sources"] == []
    assert "(no excerpts found)" in fake.requests[-1]["body"]["messages"][-1]["content"]


def test_citations_are_renumbered_after_the_sources() -> None:
    excerpts = [
        ask.Excerpt(1, "A", "a1"),
        ask.Excerpt(2, "B", "b"),
        ask.Excerpt(1, "A", "a2"),
    ]
    text, sources = chat.renumber("x [2] y [3][1] z [9] [0]", excerpts)
    assert text == "x [1] y [2][2] z  "
    assert [s.id for s in sources] == [2, 1]  # in order of first mention, a note once
    assert chat.renumber("nothing cited", excerpts) == ("nothing cited", [])


def test_changed_notes_are_embedded_before_the_answer(
    authed: TestClient, fake: Fake
) -> None:
    ready(authed, fake)
    note(authed, "Cats", "cat cat")
    fake.sse = ["Cats [1]"]
    got = put(authed, new(authed), "cat?")
    assert types(got)[0] == "indexing" and got[-1]["type"] == "done"
    paths = [r["path"] for r in fake.requests]
    assert paths.index("/embeddings") < paths.index("/chat/completions")
    assert authed.get("/api/ai/index").json() == {"total": 1, "indexed": 1}


def test_ai_off_or_unconfigured_makes_no_call(authed: TestClient, fake: Fake) -> None:
    cid = new(authed)
    r = authed.post(f"/api/chats/{cid}/ask", json={"question": "x"})
    assert r.status_code == 409 and r.json()["detail"] == {"code": "not_enabled"}
    setup_ai(authed, fake, ai_model_local="")
    r = authed.post(f"/api/chats/{cid}/ask", json={"question": "x"})
    assert r.json()["detail"] == {"code": "not_configured"}
    assert fake.requests == []


def test_a_provider_failure_is_an_error_event_and_saves_nothing(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    note(authed, "Kotki", "Kot lubi mleko")
    fake.status = 500
    cid = new(authed)
    got = put(authed, cid, "co lubi kot?")
    assert got[-1]["type"] == "error" and got[-1]["code"] == "failed"
    assert authed.get(f"/api/chats/{cid}").json()["messages"] == []


def test_a_slow_provider_is_a_timeout_event(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    monkeypatch.setattr(ai, "TIMEOUT", 0.2)
    fake.delay = 0.6
    got = put(authed, new(authed), "anything")
    assert got[-1]["type"] == "error" and got[-1]["code"] == "timeout"


def test_a_deleted_note_stays_as_a_deleted_source(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    nid = note(authed, "Kotki", "Kot lubi mleko")
    fake.sse = ["Mleko [1]"]
    cid = new(authed)
    put(authed, cid, "kot?")
    authed.delete(f"/api/notes/{nid}")
    source = authed.get(f"/api/chats/{cid}").json()["messages"][1]["sources"][0]
    assert source == {"id": nid, "title": "Kotki", "deleted": True}


def test_conversations_list_delete_and_validate(authed: TestClient, fake: Fake) -> None:
    a, b = new(authed), new(authed)
    assert [c["id"] for c in authed.get("/api/chats").json()] == [b, a]
    assert authed.delete(f"/api/chats/{a}").status_code == 204
    assert authed.delete(f"/api/chats/{a}").status_code == 404
    assert authed.get(f"/api/chats/{a}").status_code == 404
    assert authed.post(f"/api/chats/{a}/ask", json={"question": "x"}).status_code == 404
    setup_ai(authed, fake)
    assert (
        authed.post(f"/api/chats/{b}/ask", json={"question": "  "}).status_code == 422
    )
    too_long = "x" * (chat.MAX_QUESTION + 1)
    assert (
        authed.post(f"/api/chats/{b}/ask", json={"question": too_long}).status_code
        == 422
    )
    assert fake.requests == []


def test_clearing_all_data_removes_the_conversations(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    fake.sse = ["ok"]
    put(authed, new(authed), "x")
    assert authed.delete("/api/data").status_code == 204
    assert authed.get("/api/chats").json() == []


def test_chat_needs_a_login() -> None:
    from compass.main import app

    c = TestClient(app, follow_redirects=False)
    assert c.get("/api/chats").status_code == 401
    assert c.post("/api/chats").status_code == 401
    assert c.post("/api/chats/1/ask", json={"question": "x"}).status_code == 401


def test_a_conversation_can_be_renamed(authed: TestClient, fake: Fake) -> None:
    setup_ai(authed, fake)
    fake.sse = ["ok"]
    cid = new(authed)
    put(authed, cid, "pierwsze pytanie")
    r = authed.patch(f"/api/chats/{cid}", json={"title": "  Moje koty  "})
    assert r.status_code == 200 and r.json()["title"] == "Moje koty"
    assert authed.get(f"/api/chats/{cid}").json()["title"] == "Moje koty"
    assert [c["title"] for c in authed.get("/api/chats").json()] == ["Moje koty"]
    put(authed, cid, "drugie pytanie")  # a later question does not rename it
    assert authed.get(f"/api/chats/{cid}").json()["title"] == "Moje koty"


def test_a_bad_name_or_a_missing_conversation_is_refused(authed: TestClient) -> None:
    cid = new(authed)
    for bad in ("", "   ", "x" * 201, None, 5):
        assert authed.patch(f"/api/chats/{cid}", json={"title": bad}).status_code == 422
    assert authed.patch(f"/api/chats/{cid}", json={}).status_code == 422
    assert authed.patch("/api/chats/999", json={"title": "x"}).status_code == 404


def test_renaming_needs_a_login() -> None:
    from compass.main import app

    assert TestClient(app).patch("/api/chats/1", json={"title": "x"}).status_code == 401
