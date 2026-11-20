"""Translations: both languages have the same keys, every key is used, and each page speaks only its language."""

import re

import pytest

from compass.ui.i18n import DEFAULT_LANG, LANGS, STRINGS, pick_lang
from compass.ui.page import INDEX_HTML, render_index
from compass.ui.settings_page import SETTINGS_HTML


@pytest.mark.parametrize(
    ("cookie", "header", "expected"),
    [
        (None, None, "pl"),  # nothing to go on: the default
        (None, "", "pl"),
        (None, "en-US,en;q=0.9,pl;q=0.8", "en"),
        (None, "pl-PL,pl;q=0.9,en;q=0.8", "pl"),
        (None, "en;q=0.5,pl;q=0.9", "pl"),  # weights decide, not order
        (None, "de-DE,de;q=0.9,fr;q=0.8", "pl"),  # unsupported languages fall back
        (None, "de,en;q=0.4", "en"),  # first supported one wins
        (None, "EN", "en"),
        (None, "en;q=oops,pl;q=0.2", "pl"),  # a broken weight is ignored
        ("en", "pl", "en"),  # the cookie beats the header
        ("pl", "en", "pl"),
        ("xx", "en", "en"),  # an unknown cookie value is ignored
        ("", "en", "en"),
    ],
)
def test_pick_lang(cookie: str | None, header: str | None, expected: str) -> None:
    assert pick_lang(cookie, header) == expected


def test_default_is_one_of_the_languages() -> None:
    assert DEFAULT_LANG in LANGS


def test_both_languages_have_exactly_the_same_keys() -> None:
    assert set(STRINGS["pl"]) == set(STRINGS["en"])


def test_plural_forms_are_complete_for_each_language() -> None:
    assert {"one", "few", "many", "other"} <= set(
        STRINGS["pl"]["count"]
    )  # CLDR rules for pl
    assert {"one", "other"} <= set(STRINGS["en"]["count"])


def test_placeholders_match_between_languages() -> None:
    for key, pl in STRINGS["pl"].items():
        if isinstance(pl, str):
            assert re.findall(r"\{\w+\}", pl) == re.findall(
                r"\{\w+\}", STRINGS["en"][key]
            ), key


def test_every_key_used_by_the_page_exists_in_both_languages() -> None:
    pages = INDEX_HTML + SETTINGS_HTML
    used = set(re.findall(r"\[\[(\w+)\]\]", pages))
    used |= set(re.findall(r"\btr\(\"(\w+)\"", pages))
    used |= set(re.findall(r"\bT\.(\w+)", pages))
    used |= set(
        re.findall(r'"((?:import_err|field|category_err)_\w+)"', INDEX_HTML)
    )  # lookup tables
    used.discard("lang")  # filled in by the server
    assert used, "no translation keys found: the patterns need updating"
    for lang in LANGS:
        assert used <= set(STRINGS[lang]), used - set(STRINGS[lang])


def test_every_string_is_used_somewhere() -> None:
    import inspect

    from compass import auth
    from compass.ui.login import LOGIN_TEMPLATE

    text = INDEX_HTML + SETTINGS_HTML + LOGIN_TEMPLATE + inspect.getsource(auth)
    for key in STRINGS["pl"]:
        used = (
            f"[[{key}]]" in text
            or f'tr("{key}"' in text
            or f"T.{key}" in text
            or f'["{key}"]' in text
            or f'"{key}"'
            in text  # keys listed in the page's lookup tables (import errors, fields)
        )
        assert used, f"unused translation: {key}"


def test_english_page_has_no_polish_ui_text() -> None:
    page = render_index("en")
    for polish in (
        "Edytuj",
        "Usuń",
        "Zapisz",
        "Anuluj",
        "Nowa notatka",
        "Wyloguj",
        "Tagi",
        "Brak wyników",
    ):
        assert polish not in page, polish
    assert '<html lang="en" data-theme="dark">' in page
    assert "Tags (comma-separated)" in page


def test_polish_page_is_the_default_and_has_no_english_ui_text() -> None:
    page = render_index("pl")
    assert '<html lang="pl" data-theme="dark">' in page
    for english in ("Log out", "New note", "Overwrite the note?", "No results."):
        assert english not in page, english


def test_every_import_error_code_has_a_message_in_both_languages() -> None:
    import re as _re
    from pathlib import Path

    from compass.notes import transfer

    codes = {
        "not_json",
        "not_an_export",
        "invalid_file",
        "count_mismatch",
        "invalid_note",
        "invalid_conversation",
        "file_too_large",
    }
    for lang in LANGS:
        for code in codes:
            assert STRINGS[lang][f"import_err_{code}"], (lang, code)
        for field in (
            "title",
            "body",
            "tags",
            "created_at",
            "category",
            "note",
            "summary",
            "role",
            "text",
            "messages",
            "sources",
            "conversation",
            "message",
        ):
            assert STRINGS[lang][f"field_{field}"], (lang, field)
    source = Path(transfer.__file__).read_text(encoding="utf-8")
    raised = set(_re.findall(r'BadExport\(\s*"(\w+)"', source))
    assert raised <= codes, raised - codes  # a new error code needs a translation


def test_every_category_error_code_has_a_message_in_both_languages() -> None:
    from compass.api import CATEGORY_STATUS

    for lang in LANGS:
        for code in CATEGORY_STATUS:
            if (
                code == "invalid_category"
            ):  # only a note form can send it, and the form always sends a real id
                continue
            assert STRINGS[lang][f"category_err_{code}"], (lang, code)
