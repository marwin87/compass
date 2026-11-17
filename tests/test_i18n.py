import re

import pytest
from fastapi.testclient import TestClient

from compass.i18n import DEFAULT_LANG, LANGS, STRINGS, pick_lang
from compass.main import app
from compass.page import INDEX_HTML, render_index


@pytest.mark.parametrize(
    ("cookie", "header", "expected"),
    [
        (None, None, "pl"),  # nothing to go on: the default
        (None, "", "pl"),
        (None, "en-US,en;q=0.9,pl;q=0.8", "en"),
        (None, "pl-PL,pl;q=0.9,en;q=0.8", "pl"),
        (None, "en;q=0.5,pl;q=0.9", "pl"),  # weights decide, not order
        (None, "de-DE,de;q=0.9,fr;q=0.8", "pl"),  # unsupported languages fall back
        (None, "de,en;q=0.4", "en"),  # first supported one wins
        (None, "EN", "en"),
        (None, "en;q=oops,pl;q=0.2", "pl"),  # a broken weight is ignored
        ("en", "pl", "en"),  # the cookie beats the header
        ("pl", "en", "pl"),
        ("xx", "en", "en"),  # an unknown cookie value is ignored
        ("", "en", "en"),
    ],
)
def test_pick_lang(cookie: str | None, header: str | None, expected: str) -> None:
    assert pick_lang(cookie, header) == expected


def test_default_is_one_of_the_languages() -> None:
    assert DEFAULT_LANG in LANGS


def test_both_languages_have_exactly_the_same_keys() -> None:
    assert set(STRINGS["pl"]) == set(STRINGS["en"])


def test_plural_forms_are_complete_for_each_language() -> None:
    assert {"one", "few", "many", "other"} <= set(
        STRINGS["pl"]["count"]
    )  # CLDR rules for pl
    assert {"one", "other"} <= set(STRINGS["en"]["count"])


def test_placeholders_match_between_languages() -> None:
    for key, pl in STRINGS["pl"].items():
        if isinstance(pl, str):
            assert re.findall(r"\{\w+\}", pl) == re.findall(
                r"\{\w+\}", STRINGS["en"][key]
            ), key


def test_every_key_used_by_the_page_exists_in_both_languages() -> None:
    used = set(re.findall(r"\[\[(\w+)\]\]", INDEX_HTML))
    used |= set(re.findall(r"\btr\(\"(\w+)\"", INDEX_HTML))
    used |= set(re.findall(r"\bT\.(\w+)", INDEX_HTML))
    used.discard("lang")  # filled in by the server
    assert used, "no translation keys found: the patterns need updating"
    for lang in LANGS:
        assert used <= set(STRINGS[lang]), used - set(STRINGS[lang])


def test_every_string_is_used_somewhere() -> None:
    import inspect

    from compass import auth

    text = INDEX_HTML + auth.LOGIN_TEMPLATE + inspect.getsource(auth)
    for key in STRINGS["pl"]:
        used = (
            f"[[{key}]]" in text
            or f'tr("{key}"' in text
            or f"T.{key}" in text
            or f'["{key}"]' in text
        )
        assert used, f"unused translation: {key}"


def test_english_page_has_no_polish_ui_text() -> None:
    page = render_index("en")
    for polish in (
        "Edytuj",
        "Usuń",
        "Zapisz",
        "Anuluj",
        "Nowa notatka",
        "Wyloguj",
        "Tagi",
        "Brak wyników",
    ):
        assert polish not in page, polish
    assert '<html lang="en">' in page
    assert "Tags (comma-separated)" in page


def test_polish_page_is_the_default_and_has_no_english_ui_text() -> None:
    page = render_index("pl")
    assert '<html lang="pl">' in page
    for english in ("Log out", "New note", "Overwrite the note?", "No results."):
        assert english not in page, english


def test_rendered_page_has_no_unfilled_markers_and_one_script_block() -> None:
    for lang in LANGS:
        page = render_index(lang)
        assert not re.search(r"\[\[\w+\]\]", page)
        assert "/*I18N*/" not in page
        assert (
            page.count("</script>") == 1
        )  # the embedded JSON cannot end the script early


@pytest.fixture
def anon() -> TestClient:
    return TestClient(app, follow_redirects=False)


def login_cookie(c: TestClient, lang: str | None = None) -> None:
    if lang:
        c.cookies.set("lang", lang)
    assert c.post("/login", data={"password": "test-password"}).status_code == 303


def test_home_follows_accept_language(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c)
        assert 'lang="pl"' in c.get("/").text  # no header: default
        assert (
            'lang="en"'
            in c.get("/", headers={"accept-language": "en-GB,en;q=0.9"}).text
        )
        assert 'lang="pl"' in c.get("/", headers={"accept-language": "pl"}).text


def test_cookie_overrides_the_browser_language(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c, "en")
        page = c.get("/", headers={"accept-language": "pl"}).text
        assert 'lang="en"' in page and "Log out" in page
        c.cookies.set("lang", "pl")
        assert 'lang="pl"' in c.get("/", headers={"accept-language": "en"}).text


def test_unknown_cookie_value_is_ignored(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c, "<script>")
        assert 'lang="en"' in c.get("/", headers={"accept-language": "en"}).text


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


def test_export_button_is_present_in_both_languages(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c)
        pl = c.get("/").text
        assert 'href="/api/export"' in pl and "Eksportuj notatki" in pl
        assert "Pobierz wszystkie notatki jako plik JSON" in pl
        c.cookies.set("lang", "en")
        en = c.get("/").text
        assert 'href="/api/export"' in en and "Export notes" in en
        assert "Download all notes as a JSON file" in en and "Eksportuj" not in en
