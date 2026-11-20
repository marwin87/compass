import re

import pytest
from fastapi.testclient import TestClient

from compass.ui.i18n import LANGS, STRINGS
from compass.ui.page import INDEX_HTML
from compass.ui.settings_page import SETTINGS_HTML

KEYS = (
    "trash_h",
    "trash_leaving_for_chat",
    "trash_empty_btn",
    "trash_empty_state",
    "trash_pick",
    "trash_confirm_empty",
    "trash_empty_yes",
    "trash_restore",
    "trash_delete_forever",
    "trash_confirm_purge",
    "trash_purge_yes",
    "trash_deleted_on",
    "trash_days_left",
    "toast_restored",
    "toast_purged",
    "toast_trash_emptied",
    "restore_failed",
    "set_trash_days",
    "set_trash_days_desc",
    "trash_n_days",
    "trash_never",
)


@pytest.mark.parametrize("lang", LANGS)
def test_the_trash_texts_exist_in_both_languages(lang: str) -> None:
    for key in KEYS:
        assert STRINGS[lang][key].strip(), (lang, key)


def test_the_side_panel_has_a_trash_entry_and_the_list_an_empty_button() -> None:
    assert 'id="trashbtn"' in INDEX_HTML and 'id="trashn"' in INDEX_HTML
    assert 'id="trashempty"' in INDEX_HTML and "[[trash_empty_btn]]" in INDEX_HTML


def test_every_way_back_to_the_notes_leaves_the_trash() -> None:
    for name in (
        "toggleTag",
        "toggleCategory",
        "resetFilters",
        "openNew",
        "openChat",
        "openSource",
    ):
        start = INDEX_HTML.index(f"function {name}(")
        assert "leaveTrash()" in INDEX_HTML[start : start + 200], name


def test_the_trash_panel_is_read_only_and_asks_before_deleting_for_good() -> None:
    start = INDEX_HTML.index("function trashPanel(")
    panel = INDEX_HTML[start : INDEX_HTML.index("function resetFilters(")]
    assert "trash_restore" in panel and "trash_confirm_purge" in panel
    assert (
        "noteForm" not in panel
        and "/summarize" not in panel
        and "/translate" not in panel
    )
    assert "innerHTML" not in panel


def test_the_settings_page_has_the_auto_empty_control() -> None:
    assert 'id="ctl-trash-days"' in SETTINGS_HTML and 'id="trash"' in SETTINGS_HTML
    assert re.search(r'data-sec="trash"', SETTINGS_HTML)


def test_a_logged_in_page_ships_the_auto_empty_setting(authed: TestClient) -> None:
    assert '"trash_days": 0' in authed.get("/settings").text


def test_asking_the_chat_from_the_trash_says_it_is_leaving_the_trash() -> None:
    start = INDEX_HTML.index("function openChat(")
    body = INDEX_HTML[start : start + 400]
    assert "leaveTrash()" in body and 'toast(tr("trash_leaving_for_chat")' in body


def test_the_trash_panel_is_a_read_panel_so_the_hero_is_dark_in_both_themes() -> None:
    start = INDEX_HTML.index("function trashPanel(")
    assert (
        '"data-mode": "read"' in INDEX_HTML[start : start + 300]
    )  # `.card:has(.panel[data-mode="read"])` paints it
