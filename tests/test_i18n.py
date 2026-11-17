import re

import pytest
from fastapi.testclient import TestClient

from compass.i18n import DEFAULT_LANG, LANGS, STRINGS, pick_lang
from compass.main import app
from compass.page import INDEX_HTML, render_index
from compass.settings_page import SETTINGS_HTML


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
    pages = INDEX_HTML + SETTINGS_HTML
    used = set(re.findall(r"\[\[(\w+)\]\]", pages))
    used |= set(re.findall(r"\btr\(\"(\w+)\"", pages))
    used |= set(re.findall(r"\bT\.(\w+)", pages))
    used |= set(
        re.findall(r'"((?:import_err|field|category_err)_\w+)"', INDEX_HTML)
    )  # lookup tables
    used.discard("lang")  # filled in by the server
    assert used, "no translation keys found: the patterns need updating"
    for lang in LANGS:
        assert used <= set(STRINGS[lang]), used - set(STRINGS[lang])


def test_every_string_is_used_somewhere() -> None:
    import inspect

    from compass import auth

    text = INDEX_HTML + SETTINGS_HTML + auth.LOGIN_TEMPLATE + inspect.getsource(auth)
    for key in STRINGS["pl"]:
        used = (
            f"[[{key}]]" in text
            or f'tr("{key}"' in text
            or f"T.{key}" in text
            or f'["{key}"]' in text
            or f'"{key}"'
            in text  # keys listed in the page's lookup tables (import errors, fields)
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
    assert '<html lang="en" data-theme="dark">' in page
    assert "Tags (comma-separated)" in page


def test_polish_page_is_the_default_and_has_no_english_ui_text() -> None:
    page = render_index("pl")
    assert '<html lang="pl" data-theme="dark">' in page
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
        pl = c.get("/settings").text
        assert 'href="/api/export"' in pl and "Eksportuj notatki" in pl
        assert "Pobierz wszystkie notatki jako plik JSON" in pl
        c.cookies.set("lang", "en")
        en = c.get("/settings").text
        assert 'href="/api/export"' in en and "Export notes" in en
        assert "Download all notes as a JSON file" in en and "Eksportuj" not in en


def test_import_controls_are_present_in_both_languages(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c)
        pl = c.get("/settings").text
        for marker in (
            'id="import"',
            'id="importfile"',
            'id="importdialog"',
            'id="toast"',
            "Importuj notatki",
        ):
            assert marker in pl, marker
        c.cookies.set("lang", "en")
        en = c.get("/settings").text
        for marker in (
            'id="import"',
            'id="importfile"',
            'id="importdialog"',
            'id="toast"',
            "Import notes",
        ):
            assert marker in en, marker
        assert "Importuj" not in en


def test_every_import_error_code_has_a_message_in_both_languages() -> None:
    import re as _re
    from pathlib import Path

    from compass import transfer

    codes = {
        "not_json",
        "not_an_export",
        "invalid_file",
        "count_mismatch",
        "invalid_note",
        "file_too_large",
    }
    for lang in LANGS:
        for code in codes:
            assert STRINGS[lang][f"import_err_{code}"], (lang, code)
        for field in ("title", "body", "tags", "created_at", "category", "note"):
            assert STRINGS[lang][f"field_{field}"], (lang, field)
    source = Path(transfer.__file__).read_text(encoding="utf-8")
    raised = set(_re.findall(r'BadExport\(\s*"(\w+)"', source))
    assert raised <= codes, raised - codes  # a new error code needs a translation


def test_category_controls_are_present_in_both_languages(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c)
        pl = c.get("/").text
        for marker in (
            'id="catbar"',
            "Kategorie",
            "Bez kategorii",
            "Nowa kategoria",
            "Nazwa nowej kategorii",
        ):
            assert marker in pl, marker
        c.cookies.set("lang", "en")
        en = c.get("/").text
        for marker in (
            'id="catbar"',
            "Categories",
            "Uncategorized",
            "New category",
            "New category name",
        ):
            assert marker in en, marker
        assert "Kategorie" not in en and "Bez kategorii" not in en


def test_every_category_error_code_has_a_message_in_both_languages() -> None:
    from compass.api import CATEGORY_STATUS

    for lang in LANGS:
        for code in CATEGORY_STATUS:
            if (
                code == "invalid_category"
            ):  # only a note form can send it, and the form always sends a real id
                continue
            assert STRINGS[lang][f"category_err_{code}"], (lang, code)


def test_category_manager_and_clear_data_live_in_settings(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c)
        pl = c.get("/settings").text
        for marker in (
            'id="catrows"',
            'id="catnew"',
            'id="cleardialog"',
            "Zarządzaj kategoriami",
            "Wyczyść wszystkie dane",
        ):
            assert marker in pl, marker
        c.cookies.set("lang", "en")
        en = c.get("/settings").text
        for marker in (
            'id="catrows"',
            'id="catnew"',
            'id="cleardialog"',
            "Manage categories",
            "Clear all data",
        ):
            assert marker in en, marker
        assert "Zarządzaj" not in en


def test_the_notes_page_no_longer_has_the_data_tools(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c)
        page = c.get("/").text
    assert 'href="/settings#data"' in page and 'href="/settings"' in page  # the ways in
    for gone in (
        'id="import"',
        'id="importdialog"',
        'id="catdialog"',
        'href="/api/export"',
        'id="cleardialog"',
    ):
        assert gone not in page, gone


def test_redesigned_page_controls_exist_in_both_languages(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c)
        for lang, texts in (("pl", ("Czyść", "Importuj")), ("en", ("Clear", "Import"))):
            c.cookies.set("lang", lang)
            page = c.get("/").text
            for marker in (
                'id="f-all"',
                'id="f-clear"',
                'id="tagmore"',
                'id="shortcut"',
                'id="menu"',
                *texts,
            ):
                assert marker in page, (lang, marker)
        assert "https://" not in page and "http://" not in page.replace(
            "http://www.w3.org/2000/svg", ""
        )  # still no external requests


def test_skeleton_loading_is_built_in_and_respects_reduced_motion() -> None:
    assert "skeletonCard" in INDEX_HTML and "skeletonPanel" in INDEX_HTML
    assert (
        "prefers-reduced-motion:reduce" in INDEX_HTML
    )  # shimmer stops for those users
    assert "spinner" not in INDEX_HTML.lower()


def test_tab_icon_is_inline_on_both_pages(anon: TestClient) -> None:
    with anon as c:
        login = c.get("/login").text
        login_cookie(c)
        home = c.get("/").text
    for page in (login, home):
        assert 'rel="icon" type="image/svg+xml" href="data:image/svg+xml,' in page


def test_sort_control_is_present_in_both_languages(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c)
        for lang, label in (("pl", "Sortowanie"), ("en", "Sort")):
            c.cookies.set("lang", lang)
            page = c.get("/").text
            assert 'id="sort"' in page and f'aria-label="{label}"' in page, lang
        assert (
            "Nazwa A–Z" in STRINGS["pl"]["sort_title_asc"]
            and "Title A–Z" == STRINGS["en"]["sort_title_asc"]
        )


def test_the_page_embeds_the_settings_and_the_theme(anon: TestClient) -> None:
    from compass.page import render_index

    page = render_index(
        "pl",
        {"theme": "light", "reader_size": 20, "reader_width": 2, "sort": "title_asc"},
    )
    assert '<html lang="pl" data-theme="light">' in page
    assert (
        'const SETTINGS = {"theme": "light", "reader_size": 20, "reader_width": 2, "sort": "title_asc"};'
        in page
    )
    assert page.count("</script>") == 1
    default = render_index("en")
    assert (
        'data-theme="dark"' in default and '"reader_size": 17' in default
    )  # no settings given: defaults


def test_a_hostile_setting_value_cannot_end_the_script(anon: TestClient) -> None:
    from compass.page import render_index

    page = render_index(
        "pl", {"theme": "dark", "sort": "</script><script>alert(1)</script>"}
    )
    assert page.count("</script>") == 1 and "<\\/script>" in page


def test_the_served_page_follows_the_stored_theme(authed: TestClient) -> None:
    assert 'data-theme="dark"' in authed.get("/").text
    authed.put("/api/settings", json={"theme": "light", "reader_size": 21})
    page = authed.get("/").text
    assert '<html lang="pl" data-theme="light">' in page and '"reader_size": 21' in page


def test_the_theme_attribute_only_ever_holds_a_known_theme() -> None:
    from compass.page import render_index

    page = render_index("pl", {"theme": '"><script>alert(1)</script>'})
    assert (
        '<html lang="pl" data-theme="dark">' in page
        and "alert(1)</script>" not in page.split("<style>")[0]
    )


def test_language_and_theme_are_changed_only_in_settings(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c)
        notes = c.get("/").text
        settings = c.get("/settings").text
    assert (
        'data-lang="' not in notes and 'id="theme"' not in notes
    )  # no duplicates in the sidebar
    assert 'href="/settings"' in notes
    assert "ctl-lang" in settings and "ctl-theme" in settings
