from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compass.db import connect
from compass.main import app


@pytest.fixture(autouse=True)
def db_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "sub" / "compass.db"
    monkeypatch.setenv("COMPASS_DB_PATH", str(path))
    return path


def test_data_survives_reopen(db_file: Path) -> None:
    conn = connect()
    conn.execute("INSERT INTO meta VALUES ('k', 'v')")
    conn.commit()
    conn.close()

    assert db_file.exists()
    conn = connect()
    assert conn.execute("SELECT value FROM meta WHERE key='k'").fetchone() == ("v",)
    conn.close()


def test_endpoints_and_db_created(db_file: Path) -> None:
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Compass" in page.text
        assert client.get("/health").json() == {"status": "ok"}
    assert db_file.exists()
