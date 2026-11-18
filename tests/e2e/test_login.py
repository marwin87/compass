"""Flow 1: login, access control and the language of the login page."""

import re

from playwright.sync_api import Page, expect

from compass.ui.i18n import STRINGS
from tests.e2e.conftest import PASSWORD
from tests.e2e.pages import T


def sign_in(page: Page, password: str) -> None:
    page.goto("/login")
    page.get_by_placeholder(T["password_ph"]).fill(password)
    page.get_by_role("button", name=T["login_btn"]).click()


def test_a_wrong_password_stays_on_the_login_page_with_a_message(page: Page) -> None:
    sign_in(page, "to-nie-to-haslo")
    expect(page.get_by_text(T["wrong_pw"])).to_be_visible()
    expect(page).to_have_url(re.compile(r"/login$"))
    expect(
        page.get_by_placeholder(T["password_ph"])
    ).to_be_visible()  # still the form, not the app


def test_the_right_password_opens_the_notes_page(page: Page, base_url: str) -> None:
    sign_in(page, PASSWORD)
    expect(page).to_have_url(f"{base_url}/")
    expect(page.get_by_placeholder(re.compile("Szukaj"))).to_be_visible()
    expect(page.get_by_role("button", name=re.compile("Nowa notatka"))).to_be_visible()


def test_anonymous_visitors_are_sent_to_the_login_page(page: Page) -> None:
    for path in ("/", "/settings"):
        page.goto(path)
        expect(page).to_have_url(re.compile(r"/login$"))
        expect(page.get_by_role("button", name=T["login_btn"])).to_be_visible()


def test_the_session_survives_a_reload(app: Page, base_url: str) -> None:
    app.reload()
    expect(app).to_have_url(f"{base_url}/")
    expect(app.get_by_placeholder(re.compile("Szukaj"))).to_be_visible()


def test_logout_returns_to_the_login_page_and_closes_the_app(app: Page) -> None:
    app.get_by_role("button", name=T["logout"]).click()
    expect(app).to_have_url(re.compile(r"/login$"))
    app.goto("/")
    expect(app).to_have_url(re.compile(r"/login$"))
    app.goto("/settings")
    expect(app).to_have_url(re.compile(r"/login$"))


def test_the_language_buttons_on_the_login_page_switch_the_texts_and_are_remembered(
    page: Page,
) -> None:
    english = STRINGS["en"]
    page.goto("/login")
    expect(page.get_by_role("button", name=T["login_btn"])).to_be_visible()
    page.get_by_role("button", name="EN").click()
    expect(
        page.get_by_role("button", name=english["login_btn"], exact=True)
    ).to_be_visible()
    expect(page.locator("html")).to_have_attribute("lang", "en")
    page.reload()  # the choice is a cookie
    expect(
        page.get_by_role("button", name=english["login_btn"], exact=True)
    ).to_be_visible()
    page.get_by_role("button", name="PL").click()
    expect(page.get_by_role("button", name=T["login_btn"], exact=True)).to_be_visible()
