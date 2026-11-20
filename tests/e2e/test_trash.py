"""Flow: a deleted note waits in the Trash; from there it can be restored, deleted for good, or the Trash emptied."""

import re

import httpx
from playwright.sync_api import Locator, Page, expect

from tests.e2e.pages import T, card, detail_title, seed, unique


def trash_entry(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"^Kosz"))


def open_trash(page: Page) -> None:
    trash_entry(page).click()
    expect(page.locator("#count")).to_contain_text(T["trash_h"])


def test_a_deleted_note_waits_in_the_trash_and_a_restore_brings_it_back(
    app: Page, api: httpx.Client
) -> None:
    title = unique("Do kosza")
    (note_id,) = seed(api, {"title": title, "body": "tresc", "tags": ["koszowy"]})
    app.reload()
    card(app, title).click()
    app.locator("#detail").get_by_role("button", name=T["delete"], exact=True).click()
    app.get_by_role("button", name=T["yes_delete"]).click()
    expect(app.locator("#toast")).to_have_text(T["toast_deleted"])
    expect(card(app, title)).to_have_count(0)
    assert api.get(f"/api/notes/{note_id}").status_code == 404

    open_trash(app)
    expect(card(app, title)).to_be_visible()
    expect(detail_title(app, title)).to_be_visible()
    app.get_by_role("button", name=T["trash_restore"], exact=True).click()
    expect(app.locator("#toast")).to_have_text(T["toast_restored"])
    expect(card(app, title)).to_have_count(0)  # no longer in the Trash

    app.locator("#catbar").get_by_role("button", name=re.compile("Wszystkie")).click()
    expect(card(app, title)).to_be_visible()
    assert api.get(f"/api/notes/{note_id}").json()["tags"] == ["koszowy"]


def test_a_note_can_be_deleted_for_good_and_the_trash_emptied(
    app: Page, api: httpx.Client
) -> None:
    first, second, third = unique("Pierwsza"), unique("Druga"), unique("Trzecia")
    ids = seed(api, {"title": first}, {"title": second}, {"title": third})
    for note_id in ids:
        assert api.delete(f"/api/notes/{note_id}").status_code == 204
    app.reload()
    open_trash(app)
    expect(card(app, first)).to_be_visible()

    card(app, first).click()
    app.get_by_role("button", name=T["trash_delete_forever"], exact=True).click()
    expect(app.get_by_text(T["trash_confirm_purge"])).to_be_visible()
    app.get_by_role("button", name=T["back"]).click()  # backing out keeps it
    assert api.get("/api/trash/count").json() == {"count": 3}
    app.get_by_role("button", name=T["trash_delete_forever"], exact=True).click()
    app.get_by_role("button", name=T["trash_purge_yes"]).click()
    expect(app.locator("#toast")).to_have_text(T["toast_purged"])
    expect(card(app, first)).to_have_count(0)

    app.get_by_role("button", name=T["trash_empty_btn"], exact=True).click()
    app.get_by_role("button", name=T["trash_empty_yes"]).click()
    expect(app.locator("#toast")).to_have_text(T["toast_trash_emptied"])
    expect(app.locator("#results")).to_contain_text(T["trash_empty_state"])
    assert api.get("/api/trash/count").json() == {"count": 0}
