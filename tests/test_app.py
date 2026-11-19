from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compass.db import connect
from compass.main import app, create_app

PASSWORD = "test-password"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, follow_redirects=False) as c:
        yield c


def login(client: TestClient, password: str = PASSWORD) -> int:
    status: int = client.post("/login", data={"password": password}).status_code
    return status


def test_data_survives_reopen(db_file: Path) -> None:
    conn = connect()
    conn.execute("INSERT INTO meta VALUES ('k', 'v')")
    conn.commit()
    conn.close()

    assert db_file.exists()
    conn = connect()
    assert conn.execute("SELECT value FROM meta WHERE key='k'").fetchone() == ("v",)
    conn.close()


def test_health_and_login_form_are_public(client: TestClient, db_file: Path) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/login").status_code == 200
    assert db_file.exists()


@pytest.mark.parametrize("path", ["/", "/docs", "/redoc", "/openapi.json"])
def test_anonymous_is_redirected_to_login(client: TestClient, path: str) -> None:
    r = client.get(path)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_wrong_password_gives_no_access(client: TestClient) -> None:
    assert login(client, "nope") == 401
    assert client.get("/").status_code == 303


def test_login_then_logout(client: TestClient) -> None:
    assert login(client) == 303
    page = client.get("/")
    assert page.status_code == 200
    assert "Compass" in page.text
    assert client.get("/docs").status_code == 200

    assert client.post("/logout").status_code == 303
    assert client.get("/").status_code == 303


@pytest.mark.parametrize("name", ["COMPASS_PASSWORD", "COMPASS_SECRET_KEY"])
def test_refuses_to_start_without_config(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.delenv(name)
    with pytest.raises(RuntimeError, match=name):
        create_app()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("COMPASS_PASSWORD", "change-me"),
        ("COMPASS_SECRET_KEY", "change-me-too"),
        ("COMPASS_SECRET_KEY", "too-short"),
    ],
)
def test_refuses_placeholder_or_weak_secrets(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=name):
        create_app()
