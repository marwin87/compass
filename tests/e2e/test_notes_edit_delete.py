"""Flow 3: editing and deleting notes; both ask for a second, explicit confirmation."""

import re

import httpx
from playwright.sync_api import Locator, Page, expect

from tests.e2e.pages import T, card, detail_title, seed, unique


def edit_button(page: Page) -> Locator:
    return page.locator("#detail").get_by_role("button", name=T["edit"], exact=True)


def delete_button(page: Page) -> Locator:
    return page.locator("#detail").get_by_role("button", name=T["delete"], exact=True)


def open_note(page: Page, title: str) -> None:
    page.reload()
    card(page, title).click()
    detail_title(page, title).wait_for()


def test_an_edit_replaces_title_body_and_tags_after_a_confirmation(
    app: Page, api: httpx.Client
) -> None:
    old, new = unique("Stara"), unique("Nowa")
    (note_id,) = seed(api, {"title": old, "body": "stara tresc", "tags": ["a"]})
    created = api.get(f"/api/notes/{note_id}").json()["created_at"]
    open_note(app, old)

    edit_button(app).click()
    app.get_by_placeholder(T["label_title"]).fill(new)
    app.locator("#detail textarea").fill("nowa tresc")
    app.get_by_placeholder(T["label_tags"]).fill("b, c")
    app.get_by_role("button", name=T["save"], exact=True).click()

    expect(app.get_by_text(T["confirm_save"])).to_be_visible()  # nothing is written yet
    assert api.get(f"/api/notes/{note_id}").json()["title"] == old
    app.get_by_role("button", name=T["yes_overwrite"]).click()

    expect(app.locator("#toast")).to_have_text(T["toast_saved"])
    expect(detail_title(app, new)).to_be_visible()
    expect(app.locator("#detail")).to_contain_text("nowa tresc")
    expect(card(app, new)).to_be_visible()
    expect(card(app, old)).to_have_count(0)
    saved = api.get(f"/api/notes/{note_id}").json()
    assert (saved["title"], saved["body"], saved["tags"]) == (
        new,
        "nowa tresc",
        ["b", "c"],
    )
    assert saved["created_at"] == created  # an edit never changes the creation date


def test_cancelling_the_edit_keeps_the_old_text(app: Page, api: httpx.Client) -> None:
    title = unique("Bez zmian")
    (note_id,) = seed(api, {"title": title, "body": "oryginal"})
    open_note(app, title)
    edit_button(app).click()
    app.get_by_placeholder(T["label_title"]).fill("cos innego")
    app.get_by_role("button", name=T["cancel"], exact=True).click()
    expect(detail_title(app, title)).to_be_visible()
    assert api.get(f"/api/notes/{note_id}").json()["title"] == title


def test_back_from_the_confirmation_returns_to_the_form_with_the_typed_text(
    app: Page, api: httpx.Client
) -> None:
    title = unique("Wroc")
    (note_id,) = seed(api, {"title": title, "body": "oryginal"})
    open_note(app, title)
    edit_button(app).click()
    app.locator("#detail textarea").fill("pol zdania")
    app.get_by_role("button", name=T["save"], exact=True).click()
    expect(app.get_by_text(T["confirm_save"])).to_be_visible()
    app.get_by_role("button", name=T["back"]).click()
    expect(app.locator("#detail textarea")).to_have_value(
        "pol zdania"
    )  # the draft is kept
    assert api.get(f"/api/notes/{note_id}").json()["body"] == "oryginal"


def test_delete_asks_first_and_confirming_removes_the_note_everywhere(
    app: Page, api: httpx.Client
) -> None:
    keep, gone = unique("Zostaje"), unique("Znika")
    seed(
        api,
        {"title": keep, "tags": ["wspolny"]},
        {"title": gone, "tags": ["wspolny", "tylkotu"]},
    )
    ids = {n["title"]: n["id"] for n in api.get("/api/notes").json()}
    open_note(app, gone)

    delete_button(app).click()
    expect(app.get_by_text(T["confirm_delete"])).to_be_visible()
    app.get_by_role("button", name=T["back"]).click()  # backing out keeps the note
    expect(detail_title(app, gone)).to_be_visible()
    assert api.get(f"/api/notes/{ids[gone]}").status_code == 200

    delete_button(app).click()
    app.get_by_role("button", name=T["yes_delete"]).click()
    expect(app.locator("#toast")).to_have_text(T["toast_deleted"])
    expect(card(app, gone)).to_have_count(0)
    expect(card(app, keep)).to_be_visible()
    expect(
        app.locator("#tagbar").get_by_role("button", name=re.compile("#tylkotu"))
    ).to_have_count(0)  # its last note
    expect(
        app.locator("#tagbar").get_by_role("button", name=re.compile(r"#wspolny\s*1"))
    ).to_be_visible()
    assert api.get(f"/api/notes/{ids[gone]}").status_code == 404
    app.get_by_placeholder(re.compile("Szukaj")).fill(
        "znika"
    )  # and the search forgot it
    expect(app.get_by_text(T["no_results"])).to_be_visible()


def test_deleting_the_last_note_shows_the_empty_state(
    app: Page, api: httpx.Client
) -> None:
    title = unique("Ostatnia")
    seed(api, {"title": title})
    open_note(app, title)
    delete_button(app).click()
    app.get_by_role("button", name=T["yes_delete"]).click()
    expect(app.get_by_text(T["empty_none"])).to_be_visible()
    expect(app.get_by_text(T["pick_or_add"])).to_be_visible()


def test_delete_can_be_done_from_the_keyboard(app: Page, api: httpx.Client) -> None:
    title = unique("Klawiatura")
    seed(api, {"title": title})
    open_note(app, title)
    delete_button(app).focus()
    app.keyboard.press("Enter")
    expect(app.get_by_text(T["confirm_delete"])).to_be_visible()
    app.get_by_role("button", name=T["yes_delete"]).focus()
    app.keyboard.press("Enter")
    expect(card(app, title)).to_have_count(0)
