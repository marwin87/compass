"""The notes page: markers, embedded settings and theme, language choice, controls and their absence."""

import re

from fastapi.testclient import TestClient

from compass.ui.i18n import LANGS, STRINGS
from compass.ui.page import INDEX_HTML, render_index
from tests.ui.helpers import login_cookie


def test_rendered_page_has_no_unfilled_markers_and_one_script_block() -> None:
    for lang in LANGS:
        page = render_index(lang)
        assert not re.search(r"\[\[\w+\]\]", page)
        assert "/*I18N*/" not in page
        assert (
            page.count("</script>") == 1
        )  # the embedded JSON cannot end the script early


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


def test_the_notes_page_no_longer_has_the_data_tools(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c)
        page = c.get("/").text
    assert (
        'href="/settings#categories"' in page and 'href="/settings"' in page
    )  # the ways in
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
    from compass.ui.page import render_index

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
    from compass.ui.page import render_index

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
    from compass.ui.page import render_index

    page = render_index("pl", {"theme": '"><script>alert(1)</script>'})
    assert (
        '<html lang="pl" data-theme="dark">' in page
        and "alert(1)</script>" not in page.split("<style>")[0]
    )


def test_the_note_forms_get_the_markdown_editor(anon: TestClient) -> None:
    with anon as c:
        login_cookie(c)
        for lang in LANGS:
            c.cookies.set("lang", lang)
            page = c.get("/").text
            for marker in (
                "markdownEditor",
                "edWrap",
                "edTable",
                "edCallout",
                "execCommand",
            ):
                assert marker in page, (lang, marker)
            assert STRINGS[lang]["editor_preview"] in page


def test_page_has_the_notes_ui_and_never_uses_inner_html(authed: TestClient) -> None:
    page = authed.get("/")
    assert page.status_code == 200
    for marker in (
        'id="q"',  # search box
        'id="tagbar"',  # tag filter
        'id="results"',
        'id="detail"',
        'id="new"',
        "Tagi (po przecinku)",  # tag input in the add and edit forms
        "Na pewno nadpisać?",  # edit needs a second confirmation
        "Na pewno usunąć?",  # so does delete
        'href="/settings"',  # the way to import, export and manage categories
        'id="catbar"',  # category filter in the side panel
        "Kategoria",  # the category field of the note forms
        "Nowa kategoria",  # quick add from the form
    ):
        assert marker in page.text, marker
    assert "innerHTML" not in page.text  # note content must only go in via textContent
    assert (
        "fonts.googleapis" not in page.text
    )  # no external requests: notes stay on this server


def test_ai_components_show_only_when_ai_is_enabled_and_configured() -> None:
    from compass.ui.page import render_index
    from compass.ui.settings_page import render_settings

    local = {"ai_connection": "local", "ai_address": "localhost:11434/v1"}
    ready = {**local, "ai_enabled": True, "ai_model_local": "m1"}
    for render in (render_index, render_settings):
        assert "const AI_READY = false;" in render("en")  # off by default
        assert "const AI_READY = false;" in render("en", {**ready, "ai_enabled": False})
        assert "const AI_READY = false;" in render(
            "en", {**local, "ai_enabled": True}
        )  # on, but no model
        assert "const AI_READY = true;" in render("en", ready)
        assert 'class="aitag" data-ai hidden' in render(
            "en"
        )  # the logo badge starts hidden


def test_the_note_panel_has_the_summarize_control_for_ai() -> None:
    from compass.ui.page import render_index

    page = render_index("en")
    assert (
        "/summarize" in page
        and "function summarize(" in page
        and "SUMMARY_ERRORS" in page
    )
    assert (
        "aistrip" in page and "iconbtn ai" not in page
    )  # the AI actions are a strip, not toolbar icons
    assert (
        page.count('"ai_err_failed_summary"') >= 1
    )  # quoted: the usage guard looks for it
