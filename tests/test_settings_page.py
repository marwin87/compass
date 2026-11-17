import re

import pytest
from fastapi.testclient import TestClient

from compass.i18n import LANGS, STRINGS
from compass.main import app
from compass.settings_page import render_settings

SECTIONS = ("appearance", "shortcuts", "about")


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
