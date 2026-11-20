from compass.ui.i18n import STRINGS
from compass.ui.page import INDEX_HTML
from compass.ui.settings_page import SETTINGS_HTML


def test_the_note_panel_asks_for_related_notes_only_when_ai_is_ready() -> None:
    start = INDEX_HTML.index("async function loadRelated()")
    body = INDEX_HTML[start : start + 300]
    assert "if (!AI_READY || !SETTINGS.show_related) return;" in body
    assert '"/api/notes/" + note.id + "/related"' in body


def test_the_related_texts_are_translated_in_both_languages() -> None:
    for key in ("related_h", "related_more", "related_less"):
        assert STRINGS["pl"][key] and STRINGS["en"][key]
    assert (
        "{n}" in STRINGS["pl"]["related_more"]
        and "{n}" in STRINGS["en"]["related_more"]
    )


def test_only_the_first_two_related_notes_are_listed_until_expanded() -> None:
    assert "const RELATED_SHOWN = 2;" in INDEX_HTML
    assert "rel.slice(0, RELATED_SHOWN)" in INDEX_HTML


def test_related_notes_have_an_appearance_switch_that_is_on_by_default() -> None:
    from compass.settings import SPEC

    assert SPEC["show_related"].default is True
    assert 'id="ctl-related"' in SETTINGS_HTML
    assert (
        "SETTINGS.show_related && " in INDEX_HTML
        or "AI_READY && SETTINGS.show_related" in INDEX_HTML
    )


def test_a_related_note_opens_without_touching_the_search() -> None:
    start = INDEX_HTML.index("function relatedBlock()")
    block = INDEX_HTML[start : start + 1500]
    assert "openOutside(n.id)" in block and "openSource" not in block
    body = INDEX_HTML[
        INDEX_HTML.index("async function openOutside") : INDEX_HTML.index(
            "function resetFilters"
        )
    ]
    assert "state.q" not in body and "state.sel" not in body and "load(" not in body
    assert (
        'querySelector(".res.on")' in body and "scrollIntoView" in body
    )  # the chosen tile is brought into view
