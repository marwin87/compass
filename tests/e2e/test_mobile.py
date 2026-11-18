"""Flow 10: the phone layout (390 px wide): drawer, list -> detail, reading mode, forms, Settings."""

import re
from collections.abc import Iterator

import httpx
import pytest
from playwright.sync_api import Browser, Page, expect

from tests.e2e.conftest import PASSWORD
from tests.e2e.pages import T, card, detail_title, seed, unique


@pytest.fixture
def phone(browser: Browser, base_url: str) -> Iterator[Page]:
    """A logged-in page in a phone-sized browser context."""
    context = browser.new_context(
        base_url=base_url,
        viewport={"width": 390, "height": 800},
        locale="pl-PL",
        reduced_motion="reduce",
        has_touch=True,
    )
    page = context.new_page()
    page.goto("/login")
    page.get_by_placeholder(T["password_ph"]).fill(PASSWORD)
    page.get_by_role("button", name=T["login_btn"]).click()
    page.wait_for_url(f"{base_url}/")
    yield page
    context.close()


def assert_no_sideways_scroll(page: Page) -> None:
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0, f"the page is {overflow}px wider than the screen"


def test_the_menu_button_opens_the_drawer_and_the_scrim_closes_it(phone: Page) -> None:
    drawer = phone.locator("aside")
    expect(drawer).not_to_be_in_viewport()
    phone.get_by_role("button", name=T["menu_open"]).click()
    expect(drawer).to_be_in_viewport()
    expect(phone.get_by_role("button", name=re.compile("Nowa notatka"))).to_be_visible()
    phone.mouse.click(370, 400)  # the dimmed area to the right of the drawer
    expect(drawer).not_to_be_in_viewport()


def test_selecting_a_note_opens_the_detail_and_back_returns_to_the_list(
    phone: Page, api: httpx.Client
) -> None:
    title = unique("Telefon")
    seed(api, {"title": title, "body": "tresc notatki"})
    phone.reload()
    expect(phone.locator("#detail")).to_be_hidden()  # the list is shown first
    card(phone, title).click()
    expect(detail_title(phone, title)).to_be_visible()
    expect(phone.locator("#results")).to_be_hidden()
    phone.get_by_role("button", name=T["back"], exact=True).click()
    expect(phone.locator("#results")).to_be_visible()
    expect(card(phone, title)).to_be_visible()
    assert_no_sideways_scroll(phone)


def test_reading_mode_works_and_the_page_does_not_scroll_sideways(
    phone: Page, api: httpx.Client
) -> None:
    title = unique("Czytanie")
    body = (
        "## Alfa\n\n"
        + "dlugie zdanie bez konca " * 30
        + "\n\n```\n"
        + "x" * 120
        + "\n```\n\n| a | b |\n|---|---|\n| "
        + "y" * 60
        + " | 2 |"
    )
    seed(api, {"title": title, "body": body})
    phone.reload()
    card(phone, title).click()
    phone.locator("#detail").get_by_role(
        "button", name=T["reading_mode"], exact=True
    ).click()
    expect(phone.locator("#app")).to_have_class(re.compile(r"\breading\b"))
    expect(phone.locator("#detail article.md")).to_be_visible()  # not a blank page
    assert_no_sideways_scroll(phone)
    phone.get_by_role("button", name=T["reading_exit"], exact=True).click()
    expect(phone.locator("#app")).not_to_have_class(re.compile(r"\breading\b"))


def test_the_note_form_and_the_editor_toolbar_fit_the_screen(
    phone: Page, api: httpx.Client
) -> None:
    title = unique("Edycja")
    seed(api, {"title": title, "body": "tresc"})
    phone.reload()
    card(phone, title).click()
    phone.locator("#detail").get_by_role("button", name=T["edit"], exact=True).click()
    expect(phone.locator("#detail textarea")).to_be_visible()
    expect(
        phone.get_by_role("button", name=T["editor_bold"], exact=True)
    ).to_be_visible()
    expect(
        phone.get_by_role("button", name=T["editor_callout"], exact=True)
    ).to_be_visible()  # wrapped, not cut off
    assert_no_sideways_scroll(phone)


def test_the_settings_page_has_chip_navigation_and_no_sideways_scroll(
    phone: Page, api: httpx.Client
) -> None:
    for i in range(1, 41):
        assert (
            api.post(
                "/api/categories", json={"name": f"Kategoria numer {i:02d}"}
            ).status_code
            == 201
        )
    notes: list[dict[str, object]] = [
        {"title": f"n{i}", "tags": [f"tag-{i:02d}"]} for i in range(1, 41)
    ]
    seed(api, *notes)
    phone.goto("/settings")
    nav = phone.locator("#snav")
    expect(nav.get_by_role("link", name=T["settings_nav_appearance"])).to_be_visible()
    expect(nav.get_by_role("link", name=T["settings_nav_about"])).to_be_visible()
    assert_no_sideways_scroll(phone)
    for section in ("categories", "tags", "backup", "danger"):
        phone.goto(f"/settings#{section}")
        assert_no_sideways_scroll(phone)
    for rows in ("#catrows", "#tagrows"):  # long lists scroll inside their cards
        assert phone.locator(rows).evaluate(
            "el => el.scrollHeight > el.clientHeight + 50"
        )
