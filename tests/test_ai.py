import pytest
from fastapi.testclient import TestClient

from compass import ai

KEY = "sk-secret-123"


def s(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ai_enabled": True,
        "ai_connection": "openrouter",
        "ai_address": "",
        "ai_model": "m",
    }
    return {**base, **kw}


@pytest.mark.parametrize(
    ("settings", "key", "missing"),
    [
        (s(), "", ["key"]),
        (s(ai_model=""), "", ["key", "model"]),
        (s(), KEY, []),
        (s(ai_connection="local"), "", ["address"]),
        (
            s(ai_connection="local", ai_address="http://x/v1", ai_model=""),
            "",
            ["model"],
        ),
        (s(ai_connection="local", ai_address="http://x/v1"), "", []),
    ],
)
def test_missing_values(
    monkeypatch: pytest.MonkeyPatch,
    settings: dict[str, object],
    key: str,
    missing: list[str],
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", key)
    got = ai.status(settings)
    assert got["missing"] == missing and got["configured"] == (not missing)


@pytest.mark.parametrize(
    ("connection", "address", "leaves"),
    [
        ("openrouter", "", True),
        ("local", "http://localhost:11434/v1", False),
        ("local", "127.0.0.1:1234", False),
        ("local", "http://[::1]:8080/v1", False),
        ("local", "http://192.168.1.5:11434/v1", True),
        ("local", "https://llm.example.com/v1", True),
    ],
)
def test_leaves_machine(connection: str, address: str, leaves: bool) -> None:
    got = ai.status(s(ai_connection=connection, ai_address=address))
    assert got["leaves_machine"] is leaves


def test_endpoint_needs_login_and_never_returns_the_key(
    authed: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from compass.main import app

    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    assert TestClient(app).get("/api/ai/status").status_code == 401
    authed.put("/api/settings", json={"ai_model": "m", "ai_enabled": True})
    r = authed.get("/api/ai/status")
    assert r.status_code == 200 and r.json()["configured"] is True
    assert KEY not in r.text and KEY not in authed.get("/api/settings").text
    assert KEY not in authed.get("/settings").text


def test_export_has_no_ai_settings(
    authed: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    authed.put(
        "/api/settings",
        json={
            "ai_enabled": True,
            "ai_address": "http://secret-host/v1",
            "ai_model": "secret-model",
        },
    )
    text = authed.get("/api/export").text
    assert "secret-host" not in text and "secret-model" not in text and KEY not in text
    assert "ai_" not in text
