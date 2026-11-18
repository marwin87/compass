"""Flow 7: Settings are stored on the server and apply at once; language stays a cookie."""

import re

import httpx
from playwright.sync_api import Browser, Page, expect

from compass.ui.i18n import STRINGS
from tests.e2e.pages import T, book_button, detail_title, open_settings, seed, unique

EN = STRINGS["en"]


def stored(api: httpx.Client) -> dict[str, object]:
    settings: dict[str, object] = api.get("/api/settings").json()
    return settings


def test_the_theme_switch_applies_at_once_and_survives_reload_and_a_fresh_browser(
    app: Page, api: httpx.Client, browser: Browser
) -> None:
    open_settings(app, "appearance")
    expect(app.locator("html")).to_have_attribute("data-theme", "dark")
    app.locator("#ctl-theme").get_by_role("button", name=T["theme_light"]).click()
    expect(app.locator("html")).to_have_attribute("data-theme", "light")
    expect(app.locator("#toast")).to_have_text(T["settings_saved"])
    assert stored(api)["theme"] == "light"

    app.reload()
    expect(app.locator("html")).to_have_attribute(
        "data-theme", "light"
    )  # rendered by the server, no flash
    app.goto("/")
    expect(app.locator("html")).to_have_attribute("data-theme", "light")

    other = browser.new_context(
        base_url=app.url.rsplit("/", 1)[0]
    )  # a second browser sees it too
    page = other.new_page()
    page.goto("/login")
    page.get_by_placeholder(T["password_ph"]).fill("e2e-password")
    page.get_by_role("button", name=T["login_btn"]).click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    other.close()


def test_the_language_switch_changes_the_interface_and_is_remembered(app: Page) -> None:
    open_settings(app)
    app.locator("#ctl-lang").get_by_role("button", name="EN").click()
    expect(
        app.get_by_role("heading", name=EN["settings_title"], level=1)
    ).to_be_visible()
    app.goto("/")
    expect(app.get_by_role("link", name=EN["settings_title"])).to_be_visible()
    app.goto("/settings")
    app.locator("#ctl-lang").get_by_role("button", name="PL").click()
    expect(
        app.get_by_role("heading", name=T["settings_title"], level=1)
    ).to_be_visible()


def test_reading_size_and_width_set_in_settings_are_used_by_reading_mode(
    app: Page, api: httpx.Client
) -> None:
    title = unique("Rozmiar")
    seed(api, {"title": title, "body": "tekst"})
    open_settings(app, "appearance")
    plus = app.get_by_role("button", name=T["font_larger"])
    plus.click()
    plus.click()
    expect(app.locator("#ctl-size .stepval")).to_have_text("19 px")
    app.locator("#ctl-width").get_by_role("button", name=T["width_wide"]).click()
    expect(
        app.locator("#ctl-width").get_by_role("button", name=T["width_wide"])
    ).to_have_attribute("aria-pressed", "true")
    expect(app.locator("#toast")).to_have_text(T["settings_saved"])
    assert stored(api)["reader_size"] == 19
    assert stored(api)["reader_width"] == 2

    app.goto("/")
    detail_title(app, title).wait_for()
    book_button(app).click()
    expect(app.locator("#detail article.md")).to_have_css("font-size", "19px")
    expect(app.locator("#detail .card")).to_have_css("max-width", "936px")


def test_the_default_sort_set_in_settings_is_selected_on_the_notes_page(
    app: Page, api: httpx.Client
) -> None:
    seed(api, {"title": "Beta"}, {"title": "Alfa"})
    open_settings(app, "appearance")
    app.locator("#ctl-sort select").select_option(label=T["sort_title_asc"])
    expect(app.locator("#toast")).to_have_text(T["settings_saved"])
    assert stored(api)["sort"] == "title_asc"
    app.goto("/")
    expect(app.locator("#sort")).to_have_value("title_asc")
    expect(app.locator("#results .res .t")).to_have_text(["Alfa", "Beta"])


def test_a_refused_save_reverts_the_control_and_says_so(
    app: Page, api: httpx.Client
) -> None:
    open_settings(app, "appearance")
    app.route("**/api/settings", lambda route: route.fulfill(status=500, body="{}"))
    app.locator("#ctl-theme").get_by_role("button", name=T["theme_light"]).click()
    expect(app.locator("#toast")).to_have_text(T["settings_save_error"])
    expect(app.locator("html")).to_have_attribute(
        "data-theme", "dark"
    )  # back to what the server has
    expect(
        app.locator("#ctl-theme").get_by_role("button", name=T["theme_dark"])
    ).to_have_attribute("aria-pressed", "true")
    assert stored(api)["theme"] == "dark"


def test_the_settings_button_and_the_back_link_connect_the_two_pages(
    app: Page, base_url: str
) -> None:
    app.get_by_role("link", name=T["settings_title"]).click()
    expect(app).to_have_url(re.compile(r"/settings$"))
    app.get_by_role("link", name=T["settings_back"], exact=True).click()
    expect(app).to_have_url(f"{base_url}/")


def test_the_navigation_highlights_the_clicked_section_including_the_last_ones(
    app: Page,
) -> None:
    open_settings(app)
    nav = app.locator("#snav")
    for name in (
        T["settings_nav_shortcuts"],
        T["settings_nav_about"],
        T["settings_nav_appearance"],
    ):
        nav.get_by_role("link", name=name).click()
        expect(nav.get_by_role("link", name=name)).to_have_class(re.compile(r"\bon\b"))
        expect(nav.locator("a.on")).to_have_count(1)


def test_the_about_card_shows_the_real_counts(app: Page, api: httpx.Client) -> None:
    seed(
        api,
        {"title": unique("a"), "tags": ["x"]},
        {"title": unique("b"), "tags": ["x", "y"]},
    )
    open_settings(app, "about")
    card = app.locator("#aboutcard")
    expect(card).to_contain_text("2")  # notes
    expect(card).to_contain_text("compass")  # the database file
