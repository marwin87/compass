import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass import about, settings
from compass.db import connect
from compass.main import app

DEFAULTS = {
    "theme": "dark",
    "reader_size": 17,
    "reader_width": 1,
    "sort": "",
    "ai_enabled": False,
    "ai_block_page": False,
    "ai_connection": "openrouter",
    "ai_address": "",
    "ai_model_openrouter": "",
    "ai_model_local": "",
}


def put(c: TestClient, patch: Any) -> Any:
    return c.put("/api/settings", json=patch)


def test_defaults(authed: TestClient) -> None:
    r = authed.get("/api/settings")
    assert r.status_code == 200 and r.json() == DEFAULTS
    assert settings.defaults() == DEFAULTS


def test_partial_update_changes_only_the_given_keys_and_persists(
    authed: TestClient,
) -> None:
    r = put(authed, {"theme": "light", "reader_size": 20})
    assert r.status_code == 200
    assert r.json() == {**DEFAULTS, "theme": "light", "reader_size": 20}
    assert put(authed, {"sort": "title_asc"}).json() == {
        **DEFAULTS,
        "theme": "light",
        "reader_size": 20,
        "sort": "title_asc",
    }
    assert settings.current()["theme"] == "light"  # a fresh connection sees it too
    assert authed.get("/api/settings").json()["sort"] == "title_asc"


@pytest.mark.parametrize(
    ("key", "good"),
    [
        ("theme", ["dark", "light"]),
        ("reader_size", [15, 17, 22]),
        ("reader_width", [0, 1, 2]),
        ("sort", ["", "title_asc", "title_desc", "date_asc", "date_desc"]),
        ("ai_enabled", [True, False]),
        ("ai_block_page", [True, False]),
        ("ai_connection", ["openrouter", "local"]),
        ("ai_address", ["", "http://localhost:11434/v1"]),
        ("ai_model_openrouter", ["", "openai/gpt-4o-mini"]),
        ("ai_model_local", ["", "llama3"]),
    ],
)
def test_every_valid_value_is_accepted(
    authed: TestClient, key: str, good: list[object]
) -> None:
    for value in good:
        r = put(authed, {key: value})
        assert r.status_code == 200 and r.json()[key] == value


@pytest.mark.parametrize(
    ("key", "bad"),
    [
        ("theme", "blue"),
        ("theme", 1),
        ("theme", None),
        ("reader_size", 14),
        ("reader_size", 23),
        ("reader_size", 17.5),
        ("reader_size", "17"),
        ("reader_size", True),
        ("ai_enabled", "yes"),
        ("ai_enabled", 1),
        ("ai_block_page", "on"),
        ("ai_connection", "cloud"),
        ("ai_address", "x" * 201),
        ("ai_model_openrouter", 5),
        ("ai_model_local", 5),
        ("reader_width", 3),
        ("reader_width", -1),
        ("reader_width", False),
        ("sort", "random"),
        ("sort", "TITLE_ASC"),
        ("sort", None),
        ("nope", "x"),
    ],
)
def test_invalid_values_and_unknown_keys_are_rejected(
    authed: TestClient, key: str, bad: object
) -> None:
    r = put(authed, {key: bad})
    assert r.status_code == 422
    assert r.json()["detail"] == {"code": "invalid_setting", "key": key}
    assert authed.get("/api/settings").json() == DEFAULTS  # nothing changed


def test_one_bad_key_rejects_the_whole_update(authed: TestClient) -> None:
    r = put(authed, {"theme": "light", "reader_size": 99})
    assert r.status_code == 422 and r.json()["detail"]["key"] == "reader_size"
    assert authed.get("/api/settings").json()["theme"] == "dark"


def test_an_empty_update_is_a_no_op(authed: TestClient) -> None:
    put(authed, {"theme": "light"})
    assert put(authed, {}).json()["theme"] == "light"


def test_a_body_that_is_not_an_object_is_rejected(authed: TestClient) -> None:
    assert put(authed, ["theme"]).status_code == 422


def test_a_damaged_stored_value_reads_as_the_default(authed: TestClient) -> None:
    conn = connect()
    with conn:
        conn.execute("INSERT INTO settings(key, value) VALUES ('theme', 'not json')")
        conn.execute("INSERT INTO settings(key, value) VALUES ('reader_size', '99')")
        conn.execute("INSERT INTO settings(key, value) VALUES ('retired_key', '1')")
    conn.close()
    assert (
        authed.get("/api/settings").json() == DEFAULTS
    )  # unknown or invalid rows are ignored


def test_values_are_stored_as_json_text(authed: TestClient) -> None:
    put(authed, {"reader_size": 19, "theme": "light"})
    conn = connect()
    rows = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    conn.close()
    assert (
        json.loads(rows["reader_size"]) == 19 and json.loads(rows["theme"]) == "light"
    )


def test_settings_and_about_and_clear_need_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        assert anon.get("/api/settings").status_code == 401
        assert anon.put("/api/settings", json={"theme": "light"}).status_code == 401
        assert anon.get("/api/about").status_code == 401
        assert anon.delete("/api/data").status_code == 401


def test_about_reports_counts_size_path_and_version(authed: TestClient) -> None:
    authed.post("/api/categories", json={"name": "Dom"})
    authed.post("/api/notes", json={"title": "a", "tags": ["x", "y"]})
    authed.post("/api/notes", json={"title": "b"})
    data = authed.get("/api/about").json()
    assert (
        data["notes"] == 2 and data["tags"] == 2 and data["categories"] == 2
    )  # Dom + the default
    assert data["db_size_bytes"] > 0 and data["db_path"].endswith(".db")
    assert data["version"] == about.app_version() and data["version"]


def test_about_version_falls_back_to_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    from importlib.metadata import PackageNotFoundError

    def missing(_: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(about, "version", missing)
    assert about.app_version() == "dev"


def test_clear_data_removes_everything_but_keeps_the_app_working(
    authed: TestClient,
) -> None:
    authed.post("/api/categories", json={"name": "Dom"})
    authed.post("/api/notes", json={"title": "a", "tags": ["x"]})
    put(authed, {"theme": "light"})
    assert authed.delete("/api/data").status_code == 204
    assert authed.get("/api/notes").json() == []
    assert authed.get("/api/tags").json() == []
    cats = authed.get("/api/categories").json()
    assert len(cats) == 1 and cats[0]["default"] is True and cats[0]["count"] == 0
    assert (
        authed.get("/api/settings").json()["theme"] == "light"
    )  # settings are not data
    assert authed.post("/api/notes", json={"title": "again"}).status_code == 201
    assert authed.get("/api/notes", params={"q": "again"}).json()[0]["title"] == "again"
    assert authed.delete("/api/data").status_code == 204  # clearing twice is fine


def test_clear_data_empties_the_search_index(authed: TestClient) -> None:
    authed.post("/api/notes", json={"title": "Indeks", "body": "b-tree"})
    authed.delete("/api/data")
    assert authed.get("/api/notes", params={"q": "indeks"}).json() == []


def test_a_database_from_before_settings_gets_the_table_and_keeps_its_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    import sqlite3

    old = tmp_path / "old.db"
    raw = sqlite3.connect(old)
    raw.executescript(
        """
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE notes(id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                           body TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE tags(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE note_tags(note_id INTEGER NOT NULL, tag_id INTEGER NOT NULL,
                               PRIMARY KEY (note_id, tag_id));
        INSERT INTO notes(title, body, created_at)
            VALUES ('Stara notatka', 'treść', '2026-01-01T00:00:00+00:00');
        """
    )
    raw.commit()
    raw.close()
    monkeypatch.setenv("COMPASS_DB_PATH", str(old))
    assert (
        settings.current() == DEFAULTS
    )  # the table did not exist; it is created on connect
    assert settings.update({"theme": "light"})["theme"] == "light"
    with TestClient(app, follow_redirects=False) as c:
        assert c.post("/login", data={"password": "test-password"}).status_code == 303
        assert [n["title"] for n in c.get("/api/notes").json()] == ["Stara notatka"]
        assert c.get("/api/settings").json()["theme"] == "light"
        assert "Stara notatka" in c.get("/api/notes", params={"q": "stara"}).text
