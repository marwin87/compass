"""Small helpers that repeat steps the tests share. They only act; assertions stay in the tests."""

import re
import time
from collections.abc import Sequence

import httpx
from playwright.sync_api import Locator, Page

from compass.ui.i18n import STRINGS

T = STRINGS[
    "pl"
]  # the browser runs with the Polish locale; texts come from the app's own keys


def unique(prefix: str = "nota") -> str:
    """A title nobody else uses (tests never depend on each other's data)."""
    return f"{prefix}-{time.time_ns() // 1000}"


def card(page: Page, title: str) -> Locator:
    """The result card (a button) of a note in the list."""
    return page.locator("#results").get_by_role(
        "button", name=re.compile(re.escape(title))
    )


def detail_title(page: Page, title: str) -> Locator:
    return page.locator("#detail").get_by_role("heading", name=title)


def open_new_note(page: Page) -> None:
    page.get_by_role("button", name=re.compile("Nowa notatka")).click()
    page.get_by_placeholder(T["label_title"]).wait_for()


def add_note(
    page: Page,
    title: str,
    body: str = "",
    tags: Sequence[str] = (),
    category: str | None = None,
) -> None:
    """Add a note through the form and wait until it is saved and selected."""
    open_new_note(page)
    page.get_by_placeholder(T["label_title"]).fill(title)
    if body:
        page.locator("#detail textarea").fill(body)
    if tags:
        page.get_by_placeholder(T["label_tags"]).fill(", ".join(tags))
    if category:
        page.locator("#detail").get_by_label(T["label_category"]).select_option(
            label=category
        )
    page.get_by_role("button", name=T["save"], exact=True).click()
    detail_title(page, title).wait_for()


def open_settings(page: Page, section: str | None = None) -> None:
    """Go to the Settings page, optionally straight to one of its sections (its id)."""
    page.goto("/settings" + (f"#{section}" if section else ""))
    page.get_by_role("heading", name=T["settings_title"], level=1).wait_for()


def seed(api: httpx.Client, *notes: dict[str, object]) -> list[int]:
    """Create notes over the API (fast, no UI) and return their ids. Reload the page afterwards."""
    ids: list[int] = []
    for note in notes:
        r = api.post("/api/notes", json=note)
        assert r.status_code == 201, r.text
        ids.append(int(r.json()["id"]))
    return ids


def book_button(page: Page) -> Locator:
    """The reading-mode toggle in the note panel."""
    return page.locator("#detail").get_by_role(
        "button", name=T["reading_mode"], exact=True
    )
