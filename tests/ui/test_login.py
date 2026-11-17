"""The login page."""

from fastapi.testclient import TestClient

from compass.main import app


def test_login_page_is_translated_and_marks_the_active_language(
    anon: TestClient,
) -> None:
    with anon as c:
        pl = c.get("/login").text
        assert "Zaloguj" in pl and 'lang="pl"' in pl
        assert 'class="btn icon on" data-lang="pl"' in pl
        en = c.get("/login", headers={"accept-language": "en"}).text
        assert "Log in" in en and 'lang="en"' in en and "Zaloguj się" not in en
        assert 'class="btn icon on" data-lang="en"' in en
        c.cookies.set("lang", "pl")
        assert "Zaloguj" in c.get("/login", headers={"accept-language": "en"}).text


def test_wrong_password_message_is_localised(anon: TestClient) -> None:
    with anon as c:
        pl = c.post("/login", data={"password": "nope"})
        assert pl.status_code == 401 and "Nieprawidłowe hasło." in pl.text
        c.cookies.set("lang", "en")
        en = c.post("/login", data={"password": "nope"})
        assert en.status_code == 401 and "Wrong password." in en.text
        assert "Nieprawidłowe" not in en.text


def test_login_page_is_styled_and_posts_to_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        page = anon.get("/login")
    assert page.status_code == 200
    assert 'action="/login"' in page.text
    assert 'name="password"' in page.text
    assert "fonts.googleapis" not in page.text
