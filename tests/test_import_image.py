# ruff: noqa: F811  (the `fake` fixture is imported from test_translate)
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass import ai, api
from tests.test_import_word import events, of, patch_model, post
from tests.test_translate import (
    Fake,
    fake,  # noqa: F401  (the fixture, for pytest)
    rows,
    setup_ai,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"pixels"
JPG = b"\xff\xd8\xff\xe0" + b"pixels"
WEBP = b"RIFF\x10\x00\x00\x00WEBP" + b"pixels"
READ = "# Plan\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\nLogin -> Password -> Panel"


def vision(c: TestClient, f: Fake, reply: str = READ) -> None:
    setup_ai(c, f, ai_vision_model_local="v1")
    f.reply = reply


def vision_calls(f: Fake) -> list[dict[str, Any]]:
    return [r["body"] for r in f.requests if r["path"] == "/chat/completions"]


def test_an_image_is_read_by_the_vision_model_then_written_as_notes(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    vision(authed, fake)
    note = {"title": "Plan", "body": "Login -> Password -> Panel"}
    calls = patch_model(monkeypatch, lambda s, u: json.dumps([note]))
    found = events(authed, PNG, name="shot.PNG")
    assert len(of(found, "note")) == 1 and of(found, "check")
    (body,) = vision_calls(fake)  # one call: the vision model gets the image
    assert body["model"] == "v1"
    image = body["messages"][1]["content"][1]["image_url"]["url"]
    assert image.startswith("data:image/png;base64,")
    assert (
        "Login -> Password -> Panel" in calls[0][2]
    )  # its text is what the notes are written from
    assert rows() == []  # nothing saved


@pytest.mark.parametrize(
    ("raw", "name", "mime"),
    [
        (JPG, "a.jpg", "image/jpeg"),
        (JPG, "a.jpeg", "image/jpeg"),
        (WEBP, "a.webp", "image/webp"),
        (PNG, "wrong-name.jpg", "image/png"),  # the first bytes decide, not the name
    ],
)
def test_the_type_comes_from_the_bytes(
    authed: TestClient,
    fake: Fake,
    monkeypatch: pytest.MonkeyPatch,
    raw: bytes,
    name: str,
    mime: str,
) -> None:
    vision(authed, fake)
    patch_model(monkeypatch, lambda s, u: json.dumps([{"title": "T", "body": "b"}]))
    events(authed, raw, name=name)
    url = vision_calls(fake)[0]["messages"][1]["content"][1]["image_url"]["url"]
    assert url.startswith(f"data:{mime};base64,")


def test_a_fence_round_the_whole_reply_is_dropped(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    vision(authed, fake, "```markdown\n# Plan\n\ntext\n```")
    calls = patch_model(
        monkeypatch, lambda s, u: json.dumps([{"title": "T", "body": "b"}])
    )
    events(authed, PNG, name="a.png")
    assert "```" not in calls[0][2] and "# Plan" in calls[0][2]


def test_an_image_without_text_is_refused_before_any_note_is_written(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    vision(authed, fake, ai.NO_TEXT)
    calls = patch_model(monkeypatch, lambda s, u: "[]")
    r = post(authed, PNG, name="a.png")
    assert r.status_code == 422 and r.json()["detail"] == {"code": "empty"}  # type: ignore[attr-defined]
    assert calls == []


def test_no_vision_model_and_bad_bytes_are_refused_with_no_model_call(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)  # a chat model, but no vision model
    r = post(authed, PNG, name="a.png")
    assert r.status_code == 422 and r.json()["detail"] == {"code": "no_vision"}  # type: ignore[attr-defined]
    setup_ai(authed, fake, ai_vision_model_local="v1")
    r = post(authed, b"not an image", name="a.png")
    assert r.json()["detail"] == {"code": "not_image"}  # type: ignore[attr-defined]
    assert fake.requests == []


def test_ai_off_refuses_an_image_without_a_call(authed: TestClient, fake: Fake) -> None:
    setup_ai(authed, fake, ai_vision_model_local="v1", ai_enabled=False)
    r = post(authed, PNG, name="a.png")
    assert r.status_code == 409 and r.json()["detail"] == {"code": "not_enabled"}  # type: ignore[attr-defined]
    assert fake.requests == []


def test_an_image_has_a_bigger_size_limit_than_a_document(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    vision(authed, fake)
    monkeypatch.setattr(api, "MAX_WORD_BYTES", 100)
    monkeypatch.setattr(api, "MAX_IMAGE_BYTES", 1000)
    patch_model(monkeypatch, lambda s, u: json.dumps([{"title": "T", "body": "b"}]))
    assert post(authed, PNG + b"x" * 200, name="a.png").status_code == 200  # type: ignore[attr-defined]
    assert post(authed, b"x" * 200, name="a.txt").status_code == 413  # type: ignore[attr-defined]
    assert post(authed, PNG + b"x" * 2000, name="a.png").status_code == 413  # type: ignore[attr-defined]


def test_a_vision_failure_is_a_clear_error(authed: TestClient, fake: Fake) -> None:
    vision(authed, fake)
    fake.status = 500
    r = post(authed, PNG, name="a.png")
    assert r.status_code == 502 and r.json()["detail"] == {"code": "failed"}  # type: ignore[attr-defined]
