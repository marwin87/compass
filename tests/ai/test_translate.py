import json
import threading
import time
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass import ai
from compass.db import connect

KEY = "sk-secret-123"
EN = {"to": "en"}


class Fake:
    """A tiny OpenAI-compatible server on a loopback port; records what it receives."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.reply: Any = "Hello world"
        self.status = 200
        self.delay = 0.0
        self.raw: Any = None  # when set, this JSON is the whole body (embeddings)
        # when set, answers /embeddings: one vector per input text
        self.embedder: Callable[[list[str]], list[list[float]]] | None = None
        self.sse: list[str] | None = (
            None  # when set, answer as a stream of these pieces
        )
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append(
                    {
                        "path": self.path,
                        "auth": self.headers.get("Authorization"),
                        "body": body,
                    }
                )
                time.sleep(fake.delay)
                if fake.embedder is not None and self.path == "/embeddings":
                    vectors = fake.embedder(body["input"])
                    data = [{"index": i, "embedding": v} for i, v in enumerate(vectors)]
                    self.send_response(fake.status)
                    self.end_headers()
                    if fake.status == 200:
                        self.wfile.write(json.dumps({"data": data}).encode())
                    return
                if fake.sse is not None and fake.status == 200:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for piece in fake.sse:
                        event = {"choices": [{"delta": {"content": piece}}]}
                        self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    return
                self.send_response(fake.status)
                self.end_headers()
                if fake.raw is not None:
                    self.wfile.write(json.dumps(fake.raw).encode())
                elif isinstance(fake.reply, str):
                    out = {"choices": [{"message": {"content": fake.reply}}]}
                    self.wfile.write(json.dumps(out).encode())
                else:
                    self.wfile.write(b"not json")

            def log_message(self, *args: object) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"


@pytest.fixture
def fake() -> Iterator[Fake]:
    f = Fake()
    yield f
    f.server.shutdown()


def setup_ai(c: TestClient, f: Fake, **extra: object) -> None:
    patch = {
        "ai_enabled": True,
        "ai_connection": "local",
        "ai_address": f.url,
        "ai_model_local": "m1",
        "ai_model_openrouter": "m1",
        **extra,
    }
    assert c.put("/api/settings", json=patch).status_code == 200


def add(c: TestClient, body: str = "Cześć świat\n\n```py\nprint(1)\n```") -> int:
    r = c.post("/api/notes", json={"title": "T", "body": body, "tags": []})
    note_id: int = r.json()["id"]
    return note_id


def rows() -> list[tuple[object, ...]]:
    conn = connect()
    try:
        return [tuple(r) for r in conn.execute("SELECT * FROM notes").fetchall()]
    finally:
        conn.close()


def test_translates_and_changes_nothing(authed: TestClient, fake: Fake) -> None:
    setup_ai(authed, fake)
    nid = add(authed)
    before = rows()
    r = authed.post(f"/api/notes/{nid}/translate", params=EN)
    assert r.status_code == 200 and r.json() == {"lang": "en", "text": "Hello world"}
    assert rows() == before
    (req,) = fake.requests
    assert req["path"] == "/chat/completions" and req["auth"] is None
    assert req["body"]["model"] == "m1"
    system, user = (m["content"] for m in req["body"]["messages"])
    assert "Do not translate code blocks" in system and "Cześć świat" in user


def test_openrouter_sends_the_key_and_never_returns_it(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    monkeypatch.setattr(ai, "OPENROUTER_URL", fake.url)
    setup_ai(authed, fake, ai_connection="openrouter")
    r = authed.post(f"/api/notes/{add(authed)}/translate", params=EN)
    assert r.status_code == 200 and KEY not in r.text
    assert fake.requests[0]["auth"] == f"Bearer {KEY}"


def test_local_connection_never_gets_the_openrouter_key(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    setup_ai(authed, fake)
    authed.post(f"/api/notes/{add(authed)}/translate", params=EN)
    assert fake.requests[0]["auth"] is None


def test_off_or_unconfigured_makes_no_call(authed: TestClient, fake: Fake) -> None:
    nid = add(authed)
    r = authed.post(f"/api/notes/{nid}/translate", params=EN)
    assert r.status_code == 409 and r.json()["detail"] == {"code": "not_enabled"}
    setup_ai(authed, fake, ai_model_local="")
    r = authed.post(f"/api/notes/{nid}/translate", params=EN)
    assert r.status_code == 409 and r.json()["detail"] == {"code": "not_configured"}
    assert fake.requests == []


def test_provider_errors_and_garbage_are_502(authed: TestClient, fake: Fake) -> None:
    setup_ai(authed, fake)
    nid = add(authed)
    fake.status = 500
    assert authed.post(f"/api/notes/{nid}/translate", params=EN).status_code == 502
    fake.status, fake.reply = 200, None  # not JSON
    assert authed.post(f"/api/notes/{nid}/translate", params=EN).status_code == 502


def test_a_slow_provider_times_out(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    monkeypatch.setattr(ai, "TIMEOUT", 0.2)
    fake.delay = 1
    r = authed.post(f"/api/notes/{add(authed)}/translate", params=EN)
    assert r.status_code == 504 and r.json()["detail"] == {"code": "timeout"}


def test_unreachable_server_is_502(authed: TestClient, fake: Fake) -> None:
    setup_ai(authed, fake, ai_address="http://127.0.0.1:1")
    assert (
        authed.post(f"/api/notes/{add(authed)}/translate", params=EN).status_code == 502
    )


def test_empty_body_makes_no_call_and_unknown_note_is_404(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    r = authed.post(f"/api/notes/{add(authed, ' ')}/translate", params=EN)
    assert r.json() == {"lang": "en", "text": ""} and fake.requests == []
    assert authed.post("/api/notes/9999/translate", params=EN).status_code == 404


def test_login_required() -> None:
    from compass.main import app

    assert TestClient(app).post("/api/notes/1/translate", params=EN).status_code == 401


@pytest.mark.parametrize(("to", "source"), [("en", "Polish"), ("pl", "English")])
def test_the_direction_comes_from_the_client(
    authed: TestClient, fake: Fake, to: str, source: str
) -> None:
    setup_ai(authed, fake)
    r = authed.post(f"/api/notes/{add(authed)}/translate", params={"to": to})
    assert r.json()["lang"] == to
    system = fake.requests[0]["body"]["messages"][0]["content"]
    assert f"from {source} into" in system


def test_a_missing_or_unknown_direction_is_refused(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    nid = add(authed)
    assert authed.post(f"/api/notes/{nid}/translate").status_code == 422
    assert (
        authed.post(f"/api/notes/{nid}/translate", params={"to": "de"}).status_code
        == 422
    )
    assert fake.requests == []
