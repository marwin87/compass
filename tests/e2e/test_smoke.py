"""The seed test: the whole stack (server, browser, form, API, search) in one flow."""

from playwright.sync_api import Page, expect

from tests.e2e.pages import add_note, card, detail_title, unique


def test_a_note_added_through_the_form_is_found_by_search(app: Page) -> None:
    title = unique("Indeks")
    add_note(app, title, body="B-drzewo przyspiesza zapytania", tags=["sql"])

    app.get_by_placeholder("Szukaj").fill("b-drzewo")
    expect(card(app, title)).to_be_visible()
    expect(app.locator("#results .res")).to_have_count(1)
    card(app, title).click()
    expect(detail_title(app, title)).to_be_visible()
