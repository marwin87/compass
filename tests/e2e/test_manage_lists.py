"""Flow 9: managing tags and categories in Settings (rename, merge, delete, search, long lists)."""

import re

import httpx
from playwright.sync_api import Locator, Page, expect

from tests.e2e.pages import T, open_settings, seed, unique


def tag_row(page: Page, name: str) -> Locator:
    label = page.locator(".tagname").get_by_text(f"#{name}", exact=True)
    return page.locator("#tagrows li").filter(has=label)


def cat_row(page: Page, name: str) -> Locator:
    label = page.locator(".name").get_by_text(name, exact=True)
    return page.locator("#catrows li").filter(has=label)


def rename_button(row: Locator) -> Locator:
    return row.get_by_role("button", name=T["manage_rename"])


def tag_names(api: httpx.Client) -> list[str]:
    return sorted(t["name"] for t in api.get("/api/tags").json())


def test_tags_are_listed_with_counts_and_found_by_search_ignoring_case_and_accents(
    app: Page, api: httpx.Client
) -> None:
    seed(
        api,
        {"title": unique("a"), "tags": ["żółć", "sql"]},
        {"title": unique("b"), "tags": ["sql"]},
    )
    open_settings(app, "tags")
    expect(tag_row(app, "sql")).to_contain_text("2")
    expect(tag_row(app, "żółć")).to_contain_text("1")
    app.get_by_placeholder(T["tags_search_ph"]).fill("ZOLC")
    expect(app.locator("#tagrows li")).to_have_count(1)
    expect(tag_row(app, "żółć")).to_be_visible()
    app.get_by_placeholder(T["tags_search_ph"]).fill("nic-takiego")
    expect(app.get_by_text(T["tags_none_match"])).to_be_visible()


def test_tags_can_be_sorted_by_count_or_by_name(app: Page, api: httpx.Client) -> None:
    seed(
        api,
        {"title": unique("a"), "tags": ["zebra", "jablko"]},
        {"title": unique("b"), "tags": ["zebra"]},
    )
    open_settings(app, "tags")
    names = app.locator("#tagrows .tagname")
    expect(names).to_have_text(["#zebra", "#jablko"])  # most frequent first
    app.locator("#tagsort").select_option(label=T["tags_sort_name"])
    expect(names).to_have_text(["#jablko", "#zebra"])


def test_renaming_a_tag_cleans_the_name_and_updates_every_note(
    app: Page, api: httpx.Client
) -> None:
    seed(
        api,
        {"title": unique("a"), "tags": ["bazy"]},
        {"title": unique("b"), "tags": ["bazy"]},
    )
    open_settings(app, "tags")
    rename_button(tag_row(app, "bazy")).click()
    app.get_by_role("textbox", name=T["manage_rename"]).fill("  #Bazy  Danych ")
    app.get_by_role("button", name=T["save"], exact=True).click()
    expect(app.locator("#toast")).to_have_text(
        T["tags_renamed"].format(name="bazy danych")
    )
    expect(tag_row(app, "bazy danych")).to_contain_text("2")
    assert tag_names(api) == ["bazy danych"]
    app.goto(
        "/"
    )  # the notes page reflects it: the filter list and the search by the new name
    expect(
        app.locator("#tagbar").get_by_role("button", name=re.compile("#bazy danych"))
    ).to_be_visible()
    app.get_by_placeholder(re.compile("Szukaj")).fill("bazy danych")
    expect(app.locator("#results .res")).to_have_count(2)


def test_an_invalid_tag_name_is_refused_and_escape_cancels_the_edit(
    app: Page, api: httpx.Client
) -> None:
    seed(api, {"title": unique("a"), "tags": ["x"]})
    open_settings(app, "tags")
    rename_button(tag_row(app, "x")).click()
    field = app.get_by_role("textbox", name=T["manage_rename"])
    field.fill("a, b")
    app.get_by_role("button", name=T["save"], exact=True).click()
    expect(app.get_by_text(T["tags_err_name_invalid"])).to_be_visible()
    field.press("Escape")
    expect(field).to_have_count(0)
    assert tag_names(api) == ["x"]


def test_renaming_to_an_existing_tag_asks_before_merging(
    app: Page, api: httpx.Client
) -> None:
    both, only_a, only_b = unique("Obie"), unique("TylkoA"), unique("TylkoB")
    seed(
        api,
        {"title": both, "tags": ["a", "b"]},
        {"title": only_a, "tags": ["a"]},
        {"title": only_b, "tags": ["b"]},
    )
    open_settings(app, "tags")
    rename_button(tag_row(app, "a")).click()
    app.get_by_role("textbox", name=T["manage_rename"]).fill("b")
    app.get_by_role("button", name=T["save"], exact=True).click()

    question = T["tags_merge_ask"].format(
        **{"from": "a", "to": "b", "count": 2, "toCount": 2}
    )
    expect(app.get_by_text(question)).to_be_visible()  # both counts are shown
    assert tag_names(api) == ["a", "b"]  # nothing changed yet

    app.get_by_role(
        "button", name=T["back"]
    ).click()  # back returns to the field, with the original name
    field = app.get_by_role("textbox", name=T["manage_rename"])
    expect(field).to_have_value("a")
    field.fill("b")
    app.get_by_role("button", name=T["save"], exact=True).click()
    app.get_by_role("button", name=T["tags_merge_yes"]).click()

    expect(app.locator("#toast")).to_have_text(
        T["tags_merged"].format(**{"from": "a", "to": "b", "count": 3})
    )
    assert tag_names(api) == ["b"]
    expect(tag_row(app, "b")).to_contain_text("3")
    notes = {n["title"]: n["tags"] for n in api.get("/api/notes").json()}
    assert notes[both] == ["b"]  # no duplicate on the note that had both
    assert notes[only_a] == ["b"]


def test_deleting_a_tag_asks_first_and_keeps_the_notes(
    app: Page, api: httpx.Client
) -> None:
    title = unique("Zostaje")
    seed(api, {"title": title, "tags": ["tymczasowy", "stały"]})
    open_settings(app, "tags")
    tag_row(app, "tymczasowy").get_by_role("button", name=T["delete"]).click()
    expect(
        app.get_by_text(T["tags_delete_ask"].format(name="tymczasowy", count=1))
    ).to_be_visible()
    app.get_by_role("button", name=T["back"]).click()  # backing out changes nothing
    assert "tymczasowy" in tag_names(api)

    tag_row(app, "tymczasowy").get_by_role("button", name=T["delete"]).click()
    app.get_by_role("button", name=T["yes_delete"]).click()
    expect(app.locator("#toast")).to_have_text(
        T["tags_deleted"].format(name="tymczasowy", count=1)
    )
    assert tag_names(api) == ["stały"]
    assert [n["title"] for n in api.get("/api/notes").json()] == [
        title
    ]  # the note stays


def test_a_long_tag_list_scrolls_inside_its_card_and_is_capped(
    app: Page, api: httpx.Client
) -> None:
    notes = [
        {
            "id": i,
            "title": f"n{i}",
            "body": "",
            "tags": [f"tag{i:03d}"],
            "category": "",
            "created_at": "2026-11-01T10:00:00+00:00",
        }
        for i in range(1, 321)
    ]
    r = api.post(
        "/api/import",
        json={"format": "compass-export", "exported_at": "2026-11-01T10:00:00+00:00", "count": 320, "categories": [], "notes": notes},
    )  # fmt: skip
    assert r.status_code == 200, r.text
    open_settings(app, "tags")
    rows = app.locator("#tagrows")
    expect(app.locator("#tagrows li")).to_have_count(300)  # drawn at most 300
    expect(app.locator("#taghint")).to_have_text(
        T["list_capped"].format(shown=300, total=320)
    )
    assert rows.evaluate(
        "el => el.scrollHeight > el.clientHeight + 50"
    )  # the list scrolls, the page does not grow
    # the Settings page itself is about 3.5k px tall; 300 uncapped rows would add far more than the margin
    assert app.evaluate("document.documentElement.scrollHeight") < 3800
    app.get_by_placeholder(T["tags_search_ph"]).fill("tag31")
    expect(app.locator("#tagrows li")).to_have_count(10)
    expect(app.locator("#taghint")).to_have_text("")


def test_categories_can_be_added_but_not_duplicated_or_reserved(app: Page) -> None:
    open_settings(app, "categories")
    new = app.get_by_placeholder(T["category_new_ph"])
    new.fill("Praca")
    app.get_by_role("button", name=T["category_add"]).click()
    expect(cat_row(app, "Praca")).to_be_visible()
    expect(new).to_have_value("")

    new.fill("praca")  # the same name in another case
    app.get_by_role("button", name=T["category_add"]).click()
    expect(app.get_by_text(T["category_err_name_taken"])).to_be_visible()
    new.fill(T["category_default"])
    app.get_by_role("button", name=T["category_add"]).click()
    expect(app.get_by_text(T["category_err_name_reserved"])).to_be_visible()
    expect(app.locator("#catrows li")).to_have_count(2)  # the default row and "Praca"


def test_a_category_can_be_renamed_and_the_default_one_cannot_be_touched(
    app: Page, api: httpx.Client
) -> None:
    api.post("/api/categories", json={"name": "Dom"})
    open_settings(app, "categories")
    default = app.locator("#catrows li").filter(has_text=T["manage_default_note"])
    expect(default).to_be_visible()
    expect(default.get_by_role("button")).to_have_count(0)

    rename_button(cat_row(app, "Dom")).click()
    app.get_by_role("textbox", name=T["manage_rename"]).fill("Rodzina")
    app.get_by_role("button", name=T["save"], exact=True).click()
    expect(cat_row(app, "Rodzina")).to_be_visible()
    expect(cat_row(app, "Dom")).to_have_count(0)
    assert "Rodzina" in [c["name"] for c in api.get("/api/categories").json()]


def test_deleting_a_category_is_refused_when_it_has_notes_and_allowed_when_empty(
    app: Page, api: httpx.Client
) -> None:
    full = api.post("/api/categories", json={"name": "Pelna"}).json()["id"]
    api.post("/api/categories", json={"name": "Pusta"})
    seed(api, {"title": unique("w kategorii"), "category_id": full})
    open_settings(app, "categories")

    cat_row(app, "Pelna").get_by_role("button", name=T["delete"]).click()
    expect(
        app.get_by_text(T["manage_confirm_delete"].format(name="Pelna"))
    ).to_be_visible()
    app.get_by_role("button", name=T["yes_delete"]).click()
    expect(app.get_by_text(T["category_err_not_empty"].format(count=1))).to_be_visible()
    expect(cat_row(app, "Pelna")).to_be_visible()  # still there

    cat_row(app, "Pusta").get_by_role("button", name=T["delete"]).click()
    app.get_by_role("button", name=T["back"]).click()  # backing out keeps it
    expect(cat_row(app, "Pusta")).to_be_visible()
    cat_row(app, "Pusta").get_by_role("button", name=T["delete"]).click()
    app.get_by_role("button", name=T["yes_delete"]).click()
    expect(cat_row(app, "Pusta")).to_have_count(0)


def test_categories_are_found_by_search_and_the_list_scrolls(
    app: Page, api: httpx.Client
) -> None:
    for i in range(1, 61):
        assert (
            api.post("/api/categories", json={"name": f"Kat {i:02d}"}).status_code
            == 201
        )
    open_settings(app, "categories")
    rows = app.locator("#catrows")
    assert rows.evaluate(
        "el => el.scrollHeight > el.clientHeight + 50"
    )  # scrolls inside its card
    app.get_by_placeholder(T["categories_search_ph"]).fill("kat 5")
    expect(app.locator("#catrows li")).to_have_count(10)
    app.get_by_placeholder(T["categories_search_ph"]).fill("brak takiej")
    expect(app.get_by_text(T["categories_none_match"])).to_be_visible()
