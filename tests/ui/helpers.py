from fastapi.testclient import TestClient


def login_cookie(c: TestClient, lang: str | None = None) -> None:
    """Log in as the test user, optionally choosing the interface language first."""
    if lang:
        c.cookies.set("lang", lang)
    assert c.post("/login", data={"password": "test-password"}).status_code == 303
