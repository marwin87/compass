import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Must be set before `compass.main` is imported (it builds the app at import time).
# Assigned, not defaulted: a developer's real .env must not leak into the tests.
os.environ["COMPASS_PASSWORD"] = "test-password"
os.environ["COMPASS_SECRET_KEY"] = "test-secret-key"


@pytest.fixture(autouse=True)
def db_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "sub" / "compass.db"
    monkeypatch.setenv("COMPASS_DB_PATH", str(path))
    return path


@pytest.fixture
def authed() -> Iterator[TestClient]:
    from compass.main import app

    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/login", data={"password": os.environ["COMPASS_PASSWORD"]})
        assert r.status_code == 303
        yield c
