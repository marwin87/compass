# ruff: noqa: F811  (the `fake` fixture is imported from test_translate)
import pytest
from fastapi.testclient import TestClient

from compass import ai
from tests.test_translate import (
    Fake,
    add,
    fake,  # noqa: F401  (the fixture, for pytest)
    rows,
    setup_ai,
)


def test_summarizes_and_changes_nothing(authed: TestClient, fake: Fake) -> None:
    setup_ai(authed, fake)
    fake.reply = "## Summary\n\nShort.\n\n## Key points\n\n- one"
    nid = add(authed, "Docker runs containers.\n\n- images\n- volumes")
    before = rows()
    r = authed.post(f"/api/notes/{nid}/summarize")
    assert r.status_code == 200 and r.json()["text"] == fake.reply
    assert r.json()["stale"] is False and r.json()["created_at"]
    assert rows() == before  # the note itself is untouched
    (req,) = fake.requests
    assert req["path"] == "/chat/completions"
    system, user = (m["content"] for m in req["body"]["messages"])
    assert "key points" in system.lower() and "language of the note" in system
    assert (
        user == "# T\n\nDocker runs containers.\n\n- images\n- volumes"
    )  # title, then body


def test_nothing_is_called_when_ai_is_off_or_not_configured(
    authed: TestClient, fake: Fake
) -> None:
    nid = add(authed)
    r = authed.post(f"/api/notes/{nid}/summarize")
    assert r.status_code == 409 and r.json()["detail"] == {"code": "not_enabled"}
    setup_ai(authed, fake, ai_model_local="")
    r = authed.post(f"/api/notes/{nid}/summarize")
    assert r.status_code == 409 and r.json()["detail"] == {"code": "not_configured"}
    assert fake.requests == []


def test_a_missing_note_is_a_404_and_an_empty_note_makes_no_call(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    assert authed.post("/api/notes/999/summarize").status_code == 404
    nid = add(authed, "   ")
    r = authed.post(f"/api/notes/{nid}/summarize")
    assert r.status_code == 200 and r.json()["text"] == ""
    assert authed.get(f"/api/notes/{nid}/summary").json() is None  # nothing was kept
    assert fake.requests == []


def test_provider_failures_become_clear_errors(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    nid = add(authed)
    fake.status = 500
    r = authed.post(f"/api/notes/{nid}/summarize")
    assert r.status_code == 502 and r.json()["detail"] == {"code": "failed"}
    fake.status, fake.delay = 200, 0.5
    monkeypatch.setattr(ai, "SUMMARY_TIMEOUT", 0.2)
    r = authed.post(f"/api/notes/{nid}/summarize")
    assert r.status_code == 504 and r.json()["detail"] == {"code": "timeout"}
