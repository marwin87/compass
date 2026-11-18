# ruff: noqa: F811
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass import chunks
from tests.test_ask import note
from tests.test_chat import new, put
from tests.test_chunks import ready
from tests.test_translate import Fake, fake, setup_ai  # noqa: F401

NOW = "2026-01-01T00:00:00+00:00"


def conversation(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "pytanie",
        "created_at": NOW,
        "messages": [
            {"role": "user", "text": "co lubi kot?", "created_at": NOW},
            {
                "role": "assistant",
                "text": "Mleko [1].",
                "created_at": NOW,
                "sources": [{"note": 7, "title": "Kotki"}],
            },
        ],
    }
    return {**base, **over}


def doc(conversations: object = None, notes: list[dict[str, Any]] | None = None) -> str:
    items = notes if notes is not None else []
    out: dict[str, Any] = {
        "format": "compass-export",
        "count": len(items),
        "notes": items,
    }
    if conversations is not None:
        out["conversations"] = conversations
    return json.dumps(out)


def file_note(file_id: int | None, title: str) -> dict[str, Any]:
    item: dict[str, Any] = {"title": title, "body": "x", "tags": [], "created_at": NOW}
    if file_id is not None:
        item["id"] = file_id
    return item


def asked(c: TestClient, f: Fake) -> tuple[int, int]:
    """One note, one answered question that cites it; returns (note id, conversation id)."""
    setup_ai(c, f)
    nid = note(c, "Kotki", "Kot lubi mleko")
    f.sse = ["Mleko [1]."]
    cid = new(c)
    put(c, cid, "co lubi kot?")
    return nid, cid


def test_export_carries_conversations_only_when_there_are_some(
    authed: TestClient, fake: Fake
) -> None:
    note(authed, "A", "b")
    assert "conversations" not in authed.get("/api/export").json()
    nid, _ = asked(authed, fake)
    (chat,) = authed.get("/api/export").json()["conversations"]
    assert chat["title"] == "co lubi kot?"
    assert [m["role"] for m in chat["messages"]] == ["user", "assistant"]
    assert chat["messages"][1]["sources"] == [{"note": nid, "title": "Kotki"}]
    assert "sources" in chat["messages"][0] and chat["messages"][0]["sources"] == []


def test_a_source_of_a_deleted_note_is_exported_without_a_note(
    authed: TestClient, fake: Fake
) -> None:
    nid, _ = asked(authed, fake)
    authed.delete(f"/api/notes/{nid}")
    (chat,) = authed.get("/api/export").json()["conversations"]
    assert chat["messages"][1]["sources"] == [{"note": None, "title": "Kotki"}]


def test_the_round_trip_restores_conversations_and_repoints_the_sources(
    authed: TestClient, fake: Fake
) -> None:
    note(authed, "Other", "padding so that ids differ")
    asked(authed, fake)
    backup = authed.get("/api/export").text
    authed.delete("/api/data")
    note(authed, "Occupies ids", "x")  # the notes get other ids after the import
    r = authed.post("/api/import", content=backup)
    assert r.status_code == 200 and r.json() == {"imported": 2}
    (head,) = authed.get("/api/chats").json()
    thread = authed.get(f"/api/chats/{head['id']}").json()
    assert thread["title"] == "co lubi kot?"
    assert [m["text"] for m in thread["messages"]] == ["co lubi kot?", "Mleko [1]."]
    (source,) = thread["messages"][1]["sources"]
    kotki = next(n for n in authed.get("/api/notes").json() if n["title"] == "Kotki")
    assert source == {"id": kotki["id"], "title": "Kotki", "deleted": False}


def test_a_deleted_source_stays_deleted_after_the_round_trip(
    authed: TestClient, fake: Fake
) -> None:
    nid, _ = asked(authed, fake)
    authed.delete(f"/api/notes/{nid}")
    backup = authed.get("/api/export").text
    authed.post("/api/import", content=backup)
    (head,) = authed.get("/api/chats").json()
    (source,) = authed.get(f"/api/chats/{head['id']}").json()["messages"][1]["sources"]
    assert source["deleted"] is True and source["title"] == "Kotki"


def test_import_replaces_the_existing_conversations(
    authed: TestClient, fake: Fake
) -> None:
    asked(authed, fake)
    assert authed.post("/api/import", content=doc()).status_code == 200
    assert (
        authed.get("/api/chats").json() == []
    )  # a file without conversations: one to one


def test_a_file_pointing_at_a_note_the_file_lacks_shows_a_deleted_source(
    authed: TestClient,
) -> None:
    r = authed.post(
        "/api/import", content=doc([conversation()], [file_note(None, "N")])
    )
    assert r.status_code == 200
    (head,) = authed.get("/api/chats").json()
    (source,) = authed.get(f"/api/chats/{head['id']}").json()["messages"][1]["sources"]
    assert source["deleted"] is True


def test_a_file_without_conversations_still_imports(authed: TestClient) -> None:
    assert authed.post("/api/import", content=doc()).json() == {"imported": 0}


@pytest.mark.parametrize(
    ("bad", "field"),
    [
        ("text", "conversation"),
        (conversation(title=5), "title"),
        (conversation(created_at="not a date"), "created_at"),
        (conversation(messages="x"), "messages"),
        (conversation(messages=["x"]), "message"),
        (
            conversation(messages=[{"role": "bot", "text": "a", "created_at": NOW}]),
            "role",
        ),
        (
            conversation(messages=[{"role": "user", "text": "", "created_at": NOW}]),
            "text",
        ),
        (
            conversation(messages=[{"role": "user", "text": "a", "created_at": "x"}]),
            "created_at",
        ),
        (
            conversation(
                messages=[
                    {
                        "role": "user",
                        "text": "a",
                        "created_at": NOW,
                        "sources": [{"note": 1, "title": "t"}],
                    }
                ]
            ),
            "sources",
        ),
        (
            conversation(
                messages=[
                    {
                        "role": "assistant",
                        "text": "a",
                        "created_at": NOW,
                        "sources": ["x"],
                    }
                ]
            ),
            "sources",
        ),
        (
            conversation(
                messages=[
                    {
                        "role": "assistant",
                        "text": "a",
                        "created_at": NOW,
                        "sources": [{"note": "1", "title": "t"}],
                    }
                ]
            ),
            "sources",
        ),
    ],
)
def test_a_malformed_conversation_refuses_the_whole_file(
    authed: TestClient, bad: object, field: str
) -> None:
    note(authed, "Kept", "x")
    r = authed.post("/api/import", content=doc([bad]))
    assert r.status_code == 422
    assert r.json()["detail"] == {
        "code": "invalid_conversation",
        "index": 1,
        "field": field,
    }
    assert [n["title"] for n in authed.get("/api/notes").json()] == [
        "Kept"
    ]  # nothing changed


def test_conversations_must_be_a_list(authed: TestClient) -> None:
    r = authed.post("/api/import", content=doc({"title": "x"}))
    assert r.status_code == 422 and r.json()["detail"] == {"code": "invalid_file"}


def test_the_chat_index_is_rebuilt_lazily_after_an_import(
    authed: TestClient, fake: Fake
) -> None:
    s = ready(authed, fake)
    note(authed, "Cats", "cat")
    authed.post("/api/ai/index")
    backup = authed.get("/api/export").text
    authed.post("/api/import", content=backup)
    assert chunks.status(s) == {
        "total": 1,
        "indexed": 0,
    }  # the index is derived: not exported
    authed.post("/api/ai/index")
    assert chunks.status(s) == {"total": 1, "indexed": 1}
