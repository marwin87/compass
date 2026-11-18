"""Flow 6: tag and category filters, their combinations, and the sort orders."""

import re

import httpx
from playwright.sync_api import Locator, Page, expect

from tests.e2e.pages import T, card, detail_title, seed, unique


def tag(page: Page, name: str) -> Locator:
    return page.locator("#tagbar").get_by_role(
        "button", name=re.compile(rf"^#{re.escape(name)}\s*\d+$")
    )


def category(page: Page, name: str) -> Locator:
    return page.locator("#catbar").get_by_role(
        "button", name=re.compile(rf"^{re.escape(name)}\s*\d+$")
    )


def titles(page: Page) -> Locator:
    return page.locator("#results .res .t")


def make_category(api: httpx.Client, name: str) -> int:
    r = api.post("/api/categories", json={"name": name})
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def test_clicking_a_tag_filters_and_clicking_again_clears(
    app: Page, api: httpx.Client
) -> None:
    sql, cook = unique("Sql"), unique("Kuchnia")
    seed(api, {"title": sql, "tags": ["sql"]}, {"title": cook, "tags": ["jedzenie"]})
    app.reload()
    expect(app.locator("#results .res")).to_have_count(2)
    tag(app, "sql").click()
    expect(card(app, sql)).to_be_visible()
    expect(card(app, cook)).to_have_count(0)
    expect(tag(app, "sql")).to_have_class(re.compile(r"\bon\b"))
    tag(app, "sql").click()
    expect(app.locator("#results .res")).to_have_count(2)


def test_two_tags_combine_as_and(app: Page, api: httpx.Client) -> None:
    both, only_a = unique("Obie"), unique("TylkoA")
    seed(api, {"title": both, "tags": ["a", "b"]}, {"title": only_a, "tags": ["a"]})
    app.reload()
    tag(app, "a").click()
    expect(app.locator("#results .res")).to_have_count(2)
    tag(app, "b").click()
    expect(app.locator("#results .res")).to_have_count(1)
    expect(card(app, both)).to_be_visible()


def test_a_category_and_a_tag_filter_combine(app: Page, api: httpx.Client) -> None:
    work = make_category(api, "Praca")
    home = make_category(api, "Dom")
    hit, other_cat, other_tag = unique("Trafia"), unique("InnaKat"), unique("InnyTag")
    seed(
        api,
        {"title": hit, "tags": ["pilne"], "category_id": work},
        {"title": other_cat, "tags": ["pilne"], "category_id": home},
        {"title": other_tag, "tags": ["luzno"], "category_id": work},
    )
    app.reload()
    category(app, "Praca").click()
    expect(app.locator("#results .res")).to_have_count(2)
    tag(app, "pilne").click()
    expect(app.locator("#results .res")).to_have_count(1)
    expect(card(app, hit)).to_be_visible()


def test_a_filter_combines_with_a_search(app: Page, api: httpx.Client) -> None:
    first, second, third = unique("Alfa"), unique("Beta"), unique("Gamma")
    seed(
        api,
        {"title": first, "body": "wspolne slowo", "tags": ["x"]},
        {"title": second, "body": "wspolne slowo", "tags": ["y"]},
        {"title": third, "body": "inne", "tags": ["x"]},
    )
    app.reload()
    app.get_by_placeholder(re.compile("Szukaj")).fill("wspolne")
    expect(app.locator("#results .res")).to_have_count(2)
    tag(app, "x").click()
    expect(app.locator("#results .res")).to_have_count(1)
    expect(card(app, first)).to_be_visible()


def test_all_clears_filters_but_keeps_the_search_and_clear_removes_everything(
    app: Page, api: httpx.Client
) -> None:
    cat = make_category(api, "Nauka")
    one, two = unique("Jeden"), unique("Dwa")
    seed(
        api,
        {"title": one, "body": "klucz", "tags": ["t"], "category_id": cat},
        {"title": two, "body": "klucz", "tags": ["u"]},
    )
    app.reload()
    box = app.get_by_placeholder(re.compile("Szukaj"))
    box.fill("klucz")
    tag(app, "t").click()
    category(app, "Nauka").click()
    expect(app.locator("#results .res")).to_have_count(1)

    app.locator(".filters").get_by_role(
        "button", name=T["category_all"]
    ).click()  # the "all" pill
    expect(box).to_have_value("klucz")  # the text stays
    expect(app.locator("#results .res")).to_have_count(2)  # tag and category are gone

    tag(app, "t").click()
    expect(app.locator("#results .res")).to_have_count(1)
    app.locator("#f-clear").click()
    expect(box).to_have_value("")
    expect(app.locator("#results .res")).to_have_count(2)


def test_counts_next_to_tags_and_categories_are_right(
    app: Page, api: httpx.Client
) -> None:
    cat = make_category(api, "Zakupy")
    seed(
        api,
        {"title": unique("a"), "tags": ["dom"], "category_id": cat},
        {"title": unique("b"), "tags": ["dom"], "category_id": cat},
        {"title": unique("c"), "tags": ["inne"]},
    )
    app.reload()
    expect(tag(app, "dom")).to_contain_text("2")
    expect(tag(app, "inne")).to_contain_text("1")
    expect(category(app, "Zakupy")).to_contain_text("2")
    expect(
        app.locator("#catbar").get_by_role(
            "button", name=re.compile(rf"^{T['category_all']}\s*3$")
        )
    ).to_be_visible()


def choose_sort(page: Page, label: str) -> None:
    with page.expect_response(
        lambda r: "/api/notes" in r.url and r.request.method == "GET"
    ):
        page.locator("#sort").select_option(label=label)


def test_the_sort_orders_reorder_the_list(app: Page, api: httpx.Client) -> None:
    # Created in this order: Banan, Ćma, Ananas, Cytryna. Names sort accent-folded, like search: Ćma comes between Banan and Cytryna.
    seed(
        api,
        {"title": "Banan"},
        {"title": "Ćma"},
        {"title": "Ananas"},
        {"title": "Cytryna"},
    )
    app.reload()
    expect(titles(app)).to_have_text(
        ["Cytryna", "Ananas", "Ćma", "Banan"]
    )  # default: newest first

    choose_sort(app, T["sort_title_asc"])
    expect(titles(app)).to_have_text(["Ananas", "Banan", "Ćma", "Cytryna"])
    expect(app.locator("#sortbox")).to_have_class(
        re.compile(r"\bon\b")
    )  # an active sort is highlighted
    choose_sort(app, T["sort_title_desc"])
    expect(titles(app)).to_have_text(["Cytryna", "Ćma", "Banan", "Ananas"])
    choose_sort(app, T["sort_date_asc"])
    expect(titles(app)).to_have_text(["Banan", "Ćma", "Ananas", "Cytryna"])
    choose_sort(app, T["sort_date_desc"])
    expect(titles(app)).to_have_text(["Cytryna", "Ananas", "Ćma", "Banan"])
    choose_sort(app, T["sort_default"])
    expect(app.locator("#sortbox")).not_to_have_class(re.compile(r"\bon\b"))


def test_the_chosen_sort_is_saved_on_the_server_and_survives_reload(
    app: Page, api: httpx.Client
) -> None:
    seed(api, {"title": "Beta"}, {"title": "Alfa"})
    app.reload()
    choose_sort(app, T["sort_title_asc"])
    expect(titles(app)).to_have_text(["Alfa", "Beta"])
    app.reload()
    expect(app.locator("#sort")).to_have_value("title_asc")
    expect(titles(app)).to_have_text(["Alfa", "Beta"])
    assert api.get("/api/settings").json()["sort"] == "title_asc"


def test_the_arrow_keys_move_through_the_list_and_keep_the_card_in_view(
    app: Page, api: httpx.Client
) -> None:
    notes: list[dict[str, object]] = [
        {"title": f"Nota {i:02d}", "body": "tresc"} for i in range(1, 21)
    ]
    seed(api, *notes)
    app.reload()
    app.locator("#count").click()  # focus on the page, not on a field
    expect(app.locator("#results .res.on .t")).to_have_text(
        "Nota 20"
    )  # newest first, first one is open
    app.keyboard.press("ArrowDown")
    expect(app.locator("#results .res.on .t")).to_have_text("Nota 19")
    expect(detail_title(app, "Nota 19")).to_be_visible()
    for _ in range(25):
        app.keyboard.press("ArrowDown")
    expect(app.locator("#results .res.on .t")).to_have_text(
        "Nota 01"
    )  # stops at the last note
    expect(app.locator("#results .res.on")).to_be_in_viewport()
    for _ in range(25):
        app.keyboard.press("ArrowUp")
    expect(app.locator("#results .res.on .t")).to_have_text("Nota 20")
