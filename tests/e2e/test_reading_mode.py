"""Flow 5: reading mode, its controls and the table of contents."""

import re

import httpx2 as httpx
from playwright.sync_api import Locator, Page, expect

from tests.e2e.pages import T, card, detail_title, seed, unique

SECTIONS = ("Alfa", "Beta", "Gamma", "Delta")


def long_note(title: str) -> dict[str, object]:
    body = "\n\n".join(
        f"## {name}\n\n"
        + "\n\n".join(f"Akapit {i} sekcji {name}. " + "tekst " * 40 for i in range(6))
        for name in SECTIONS
    )
    return {"title": title, "body": body, "tags": []}


def book(page: Page) -> Locator:
    return page.locator("#detail").get_by_role(
        "button", name=T["reading_mode"], exact=True
    )


def enter(page: Page, title: str) -> None:
    page.reload()
    detail_title(page, title).wait_for()
    book(page).click()
    expect(page.locator("#app")).to_have_class(re.compile(r"\breading\b"))


def test_the_book_icon_enters_reading_mode_and_hides_the_chrome(
    app: Page, api: httpx.Client
) -> None:
    title = unique("Czytanie")
    seed(api, {"title": title, "body": "Tresc do spokojnego czytania."})
    app.reload()
    detail_title(app, title).wait_for()
    expect(book(app)).to_have_attribute("aria-pressed", "false")
    book(app).click()

    expect(app.locator("#app")).to_have_class(re.compile(r"\breading\b"))
    expect(book(app)).to_have_attribute("aria-pressed", "true")
    expect(app.locator("aside")).to_be_hidden()
    expect(app.locator(".listcol")).to_be_hidden()
    expect(app.locator(".topbar")).to_be_hidden()
    expect(app.locator("#readbar")).to_be_visible()
    expect(app.locator("#detail article.md")).to_contain_text("spokojnego czytania")


def test_the_three_ways_out_of_reading_mode(app: Page, api: httpx.Client) -> None:
    title = unique("Wyjscie")
    seed(api, {"title": title, "body": "tekst"})
    enter(app, title)
    app.keyboard.press("Escape")  # 1. the Escape key
    expect(app.locator("#app")).not_to_have_class(re.compile(r"\breading\b"))
    expect(app.locator("aside")).to_be_visible()

    book(app).click()
    expect(app.locator("#app")).to_have_class(re.compile(r"\breading\b"))
    app.get_by_role(
        "button", name=T["reading_exit"], exact=True
    ).click()  # 2. the Esc / Exit button
    expect(app.locator("#app")).not_to_have_class(re.compile(r"\breading\b"))

    book(app).click()
    book(app).click()  # 3. the lit book icon is a toggle
    expect(app.locator("#app")).not_to_have_class(re.compile(r"\breading\b"))
    expect(book(app)).to_have_attribute("aria-pressed", "false")


def test_the_font_size_buttons_change_the_text_and_are_saved(
    app: Page, api: httpx.Client
) -> None:
    title = unique("Rozmiar")
    seed(api, {"title": title, "body": "tekst"})
    enter(app, title)
    article = app.locator("#detail article.md")
    expect(article).to_have_css("font-size", "17px")

    app.get_by_role("button", name=T["font_larger"]).click()
    expect(article).to_have_css("font-size", "18px")
    with app.expect_response(
        lambda r: r.url.endswith("/api/settings") and r.request.method == "PUT"
    ):
        app.get_by_role(
            "button", name=T["font_larger"]
        ).click()  # saved a moment after the last click
    expect(article).to_have_css("font-size", "19px")
    assert api.get("/api/settings").json()["reader_size"] == 19
    app.get_by_role("button", name=T["font_smaller"]).click()
    expect(article).to_have_css("font-size", "18px")


def test_the_width_button_cycles_through_three_widths(
    app: Page, api: httpx.Client
) -> None:
    title = unique("Szerokosc")
    seed(api, {"title": title, "body": "tekst"})
    enter(app, title)
    box = app.locator("#detail .card")
    expect(box).to_have_css("max-width", "816px")  # 760 px of text plus the padding
    app.get_by_role("button", name=T["width_toggle"]).click()
    expect(box).to_have_css("max-width", "936px")
    app.get_by_role("button", name=T["width_toggle"]).click()
    expect(box).to_have_css("max-width", "736px")


def test_a_long_note_gets_contents_that_scroll_to_the_section_and_follow_the_reader(
    app: Page, api: httpx.Client
) -> None:
    title = unique("Dluga")
    seed(api, long_note(title))
    enter(app, title)

    toc = app.locator("#detail .toc")
    expect(toc.get_by_role("link")).to_have_count(4)
    expect(toc).to_have_attribute("open", "")  # open while reading
    link = toc.get_by_role("link", name="Gamma")
    link.click()
    heading = app.locator("#detail article").get_by_role("heading", name="Gamma")
    expect(heading).to_be_in_viewport()
    expect(link).to_have_class(
        re.compile(r"\bon\b")
    )  # the clicked section is the highlighted one
    expect(toc.locator("a.on")).to_have_count(1)


def test_contents_are_collapsed_in_the_normal_view_and_a_short_note_has_none(
    app: Page, api: httpx.Client
) -> None:
    long_title, short_title = unique("Dluga"), unique("Krotka")
    seed(
        api,
        long_note(long_title),
        {"title": short_title, "body": "## Jedyny naglowek\n\ntekst"},
    )
    app.reload()
    card(app, short_title).click()
    detail_title(app, short_title).wait_for()
    expect(app.locator("#detail .toc")).to_have_count(0)  # fewer than three headings

    card(app, long_title).click()
    detail_title(app, long_title).wait_for()
    toc = app.locator("#detail .toc")
    expect(toc).not_to_have_attribute("open", "")
    toc.get_by_text(T["toc_title"]).click()
    expect(toc.get_by_role("link", name="Alfa")).to_be_visible()


def test_the_arrow_keys_do_not_switch_notes_while_reading(
    app: Page, api: httpx.Client
) -> None:
    first, second = unique("Pierwsza"), unique("Druga")
    seed(api, {"title": first, "body": "a"}, {"title": second, "body": "b"})
    app.reload()
    app.locator("#results").get_by_role(
        "button", name=re.compile(re.escape(first))
    ).click()
    detail_title(app, first).wait_for()
    book(app).click()
    app.keyboard.press("ArrowUp")
    app.keyboard.press("ArrowDown")
    expect(detail_title(app, first)).to_be_visible()
    expect(detail_title(app, second)).to_have_count(0)


def test_editing_a_note_leaves_reading_mode(app: Page, api: httpx.Client) -> None:
    title = unique("Edycja")
    seed(api, {"title": title, "body": "tekst"})
    enter(app, title)
    app.locator("#detail").get_by_role("button", name=T["edit"], exact=True).click()
    expect(app.locator("#app")).not_to_have_class(re.compile(r"\breading\b"))
    expect(app.locator("#detail textarea")).to_be_visible()
