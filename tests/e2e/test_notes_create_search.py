"""Flow 2: create a note through the form, then find it by search."""

import re

import httpx
from playwright.sync_api import Page, expect

from tests.e2e.pages import T, add_note, card, open_new_note, seed, unique


def search(page: Page, text: str) -> None:
    page.get_by_placeholder(re.compile("Szukaj")).fill(text)


def test_a_new_note_appears_selected_with_its_tags_category_and_counts(
    app: Page, api: httpx.Client
) -> None:
    api.post("/api/categories", json={"name": "Dom"})
    app.reload()  # the form lists the categories loaded with the page
    title = unique("Zakupy")
    add_note(app, title, body="mleko i chleb", tags=["listy", "dom"], category="Dom")

    expect(app.locator("#toast")).to_have_text(T["toast_created"])
    expect(card(app, title)).to_have_class(
        re.compile(r"\bon\b")
    )  # the new card is the selected one
    detail = app.locator("#detail")
    expect(detail).to_contain_text("mleko i chleb")
    expect(detail.get_by_role("button", name="#listy")).to_be_visible()
    expect(detail.get_by_text("Dom", exact=True)).to_be_visible()
    expect(
        app.locator("#tagbar").get_by_role("button", name=re.compile(r"#listy\s*1"))
    ).to_be_visible()
    expect(
        app.locator("#catbar").get_by_role("button", name=re.compile(r"Dom\s*1"))
    ).to_be_visible()
    expect(app.locator("#count")).to_contain_text("1 wynik")


def test_an_empty_title_is_refused_and_nothing_is_saved(app: Page) -> None:
    open_new_note(app)
    app.get_by_role("button", name=T["save"], exact=True).click()
    expect(app.locator("#detail").get_by_text(T["empty_title"])).to_be_visible()
    expect(app.locator("#results .res")).to_have_count(0)
    app.get_by_role("button", name=T["cancel"]).click()
    expect(app.get_by_text(T["empty_none"])).to_be_visible()


def test_search_finds_by_body_tag_and_prefix(app: Page, api: httpx.Client) -> None:
    index, recipe = unique("Indeks"), unique("Przepis")
    seed(
        api,
        {"title": index, "body": "b-tree przyspiesza zapytania", "tags": ["sql"]},
        {"title": recipe, "body": "maka i jajka", "tags": ["kuchnia"]},
    )
    app.reload()
    expect(app.locator("#results .res")).to_have_count(2)

    search(app, "przyspiesza")  # a body word
    expect(card(app, index)).to_be_visible()
    expect(card(app, recipe)).to_have_count(0)
    search(app, "kuchnia")  # a tag
    expect(card(app, recipe)).to_be_visible()
    expect(card(app, index)).to_have_count(0)
    search(app, "indek")  # the start of a word
    expect(card(app, index)).to_be_visible()
    expect(app.locator("#results .res")).to_have_count(1)


def test_typos_and_missing_polish_letters_still_find_the_note(
    app: Page, api: httpx.Client
) -> None:
    index, complexity = unique("Indeks"), unique("Złożoność")
    seed(api, {"title": index, "body": ""}, {"title": complexity, "body": ""})
    app.reload()
    search(app, "indkes")  # two letters swapped
    expect(card(app, index)).to_be_visible()
    expect(app.locator("#results .res")).to_have_count(1)
    search(app, "zlozonosc")  # no Polish letters
    expect(card(app, complexity)).to_be_visible()
    expect(app.locator("#results .res")).to_have_count(1)


def test_a_query_without_matches_says_so(app: Page, api: httpx.Client) -> None:
    seed(api, {"title": unique("Cokolwiek")})
    app.reload()
    search(app, "qqqzzzxxx")
    expect(app.get_by_text(T["no_results"])).to_be_visible()
    expect(app.locator("#results .res")).to_have_count(0)


def test_matches_are_highlighted_in_the_list(app: Page, api: httpx.Client) -> None:
    seed(api, {"title": unique("Transakcje"), "body": "acid i izolacja"})
    app.reload()
    search(app, "izolacja")
    expect(app.locator("#results mark")).to_have_text("izolacja")


def test_escape_clears_the_search(app: Page, api: httpx.Client) -> None:
    first, second = unique("Pierwsza"), unique("Druga")
    seed(api, {"title": first}, {"title": second})
    app.reload()
    box = app.get_by_placeholder(re.compile("Szukaj"))
    box.fill("pierwsza")
    expect(app.locator("#results .res")).to_have_count(1)
    box.press("Escape")
    expect(box).to_have_value("")
    expect(app.locator("#results .res")).to_have_count(2)


def test_keyboard_shortcuts_focus_the_search_and_open_a_new_note(
    app: Page, api: httpx.Client
) -> None:
    seed(api, {"title": unique("Skrot")})
    app.reload()
    box = app.get_by_placeholder(re.compile("Szukaj"))
    app.locator("#count").click()  # take the focus away from the search box
    expect(box).not_to_be_focused()
    app.keyboard.press("/")
    expect(box).to_be_focused()
    app.locator("#count").click()
    app.keyboard.press("Control+k")
    expect(box).to_be_focused()
    app.locator("#count").click()
    app.keyboard.press("n")
    expect(app.get_by_placeholder(T["label_title"])).to_be_visible()
