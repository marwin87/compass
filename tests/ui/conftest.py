import pytest
from fastapi.testclient import TestClient

from compass.main import app


@pytest.fixture
def anon() -> TestClient:
    """A client that is not logged in (pages and the login form are tested through it)."""
    return TestClient(app, follow_redirects=False)
