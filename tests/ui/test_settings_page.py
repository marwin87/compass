import re

import pytest
from fastapi.testclient import TestClient

from compass.main import app
from compass.ui.i18n import LANGS, STRINGS
from compass.ui.settings_page import render_settings
from tests.ui.helpers import login_cookie

SECTIONS = (
    "appearance",
    "categories",
    "tags",
    "backup",
    "shortcuts",
    "danger",
    "about",
)


def test_the_page_needs_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        r = anon.get("/settings")
    assert r.status_code == 303 and r.headers["location"] == "/login"


@pytest.mark.parametrize("lang", LANGS)
def test_it_renders_every_section_in_the_chosen_language(
    authed: TestClient, lang: str
) -> None:
    authed.cookies.set("lang", lang)
    page = authed.get("/settings").text
    assert f'<html lang="{lang}"' in page
    for section in SECTIONS:
        assert f'id="{section}"' in page and f'href="#{section}"' in page, section
    assert STRINGS[lang]["settings_title"] in page
    assert (
        STRINGS[lang]["set_theme"] in page
        and STRINGS[lang]["settings_nav_about"] in page
    )
    assert not re.search(r"\[\[\w+\]\]", page) and "/*" not in page.split("<script>")[0]
    assert page.count("</script>") == 1


def test_it_follows_the_browser_language_when_there_is_no_cookie(
    authed: TestClient,
) -> None:
    assert (
        'lang="en"'
        in authed.get("/settings", headers={"accept-language": "en-GB,en;q=0.9"}).text
    )


def test_it_embeds_the_stored_settings_and_theme(authed: TestClient) -> None:
    authed.put(
        "/api/settings", json={"theme": "light", "reader_size": 21, "sort": "date_asc"}
    )
    page = authed.get("/settings").text
    assert '<html lang="pl" data-theme="light">' in page
    assert '"reader_size": 21' in page and '"sort": "date_asc"' in page


def test_it_makes_no_external_request_and_has_the_tab_icon() -> None:
    page = render_settings("en")
    assert 'rel="icon"' in page
    assert "https://" not in page and "http://" not in page.replace(
        "http://www.w3.org/2000/svg", ""
    )


def test_the_notes_page_links_to_settings(authed: TestClient) -> None:
    assert 'href="/settings"' in authed.get("/").text


def test_every_new_setting_in_the_registry_has_a_control_label() -> None:
    from compass import settings

    page = render_settings("pl")
    for (
        key
    ) in settings.SPEC:  # a key without a control would be a setting nobody can change
        assert f'"{key}"' in page, key


@pytest.mark.parametrize("lang", LANGS)
def test_the_logo_and_tagline_are_always_on_the_settings_page(
    authed: TestClient, lang: str
) -> None:
    authed.cookies.set("lang", lang)
    page = authed.get("/settings").text
    assert 'class="slogo" href="/"' in page and ">Compass<" in page
    assert STRINGS[lang]["tagline"] in page  # the same description as on the notes page


@pytest.mark.parametrize("lang", LANGS)
def test_the_tags_section_has_its_controls(authed: TestClient, lang: str) -> None:
    authed.cookies.set("lang", lang)
    page = authed.get("/settings").text
    for marker in (
        'id="tagrows"',
        'id="tagsearch"',
        'id="tagsort"',
        'id="taghint"',
        'id="tagmsg"',
    ):
        assert marker in page, marker
    assert STRINGS[lang]["tags_manage_title"] in page


def test_the_notes_page_links_to_tag_management(authed: TestClient) -> None:
    notes_page = authed.get("/").text
    assert (
        'href="/settings#tags"' in notes_page
        and 'href="/settings#categories"' in notes_page
    )


@pytest.mark.parametrize("lang", LANGS)
def test_the_danger_zone_is_always_right_above_about(
    authed: TestClient, lang: str
) -> None:
    authed.cookies.set("lang", lang)
    page = authed.get("/settings").text
    order = [
        m.group(1) for m in re.finditer(r'<section class="ssec" id="(\w+)">', page)
    ]
    assert order[-2:] == ["danger", "about"], (
        order
    )  # the clear-all button never sits among the everyday settings
    assert order == list(SECTIONS)
    nav = re.findall(r'<a href="#(\w+)" data-sec="\w+">', page)
    assert nav == order  # the navigation lists them in the same order
    section = page.split('id="danger"')[1].split('id="about"')[0]
    assert 'id="clearbtn"' in section and STRINGS[lang]["data_danger_h"] in section
    for other in (
        "categories",
        "tags",
        "backup",
    ):  # and it is in none of the everyday sections
        body = page.split(f'id="{other}"')[1].split("</section>")[0]
        assert 'id="clearbtn"' not in body, other


@pytest.mark.parametrize("lang", LANGS)
def test_the_categories_section_is_its_own_section_with_search(
    authed: TestClient, lang: str
) -> None:
    authed.cookies.set("lang", lang)
    page = authed.get("/settings").text
    section = page.split('id="categories"')[1].split("</section>")[0]
    for marker in (
        'id="catnew"',
        'id="catadd"',
        'id="catsearch"',
        'id="catrows"',
        'class="mgrlist"',
    ):
        assert marker in section, marker
    assert STRINGS[lang]["categories_search_ph"] in section
    backup = page.split('id="backup"')[1].split("</section>")[0]
    assert (
        'id="exportlink"' in backup
        and 'id="import"' in backup
        and "catrows" not in backup
    )


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
