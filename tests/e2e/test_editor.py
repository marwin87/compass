"""Flow 4: the Markdown toolbar and the preview tab of the note forms."""

import re

import pytest
from playwright.sync_api import Locator, Page, expect

from tests.e2e.pages import T, detail_title, open_new_note, unique

MARKDOWN = """# Tytuł

## Sekcja

- a
- b

> [!TIP]
> wskazówka

```python
print(1)
```

| a | b |
|---|---|
| 1 | 2 |

<b>surowy</b> **gruby**"""


def textarea(page: Page) -> Locator:
    return page.locator("#detail textarea")


def select(ta: Locator, start: int, end: int) -> None:
    """Select a range inside the textarea (what a mouse drag would do)."""
    ta.evaluate(
        "(el, [a, b]) => { el.focus(); el.setSelectionRange(a, b); }", [start, end]
    )


def tool(page: Page, key: str) -> Locator:
    return page.get_by_role("button", name=T[key], exact=True)


def test_the_form_has_the_tabs_and_the_toolbar(app: Page) -> None:
    open_new_note(app)
    expect(app.get_by_role("tab", name=T["editor_write"])).to_have_attribute(
        "aria-selected", "true"
    )
    expect(app.get_by_role("tab", name=T["editor_preview"])).to_be_visible()
    for key in (
        "bold",
        "italic",
        "strike",
        "h2",
        "h3",
        "ul",
        "ol",
        "code",
        "quote",
        "link",
        "table",
        "callout",
    ):
        expect(tool(app, f"editor_{key}")).to_be_visible()


def test_bold_wraps_the_selection_and_the_second_click_unwraps_it(app: Page) -> None:
    open_new_note(app)
    ta = textarea(app)
    ta.fill("hello world")
    select(ta, 6, 11)
    tool(app, "editor_bold").click()
    expect(ta).to_have_value("hello **world**")
    expect(ta).to_be_focused()  # the toolbar never steals the focus
    tool(app, "editor_bold").click()
    expect(ta).to_have_value("hello world")


def test_ctrl_b_and_ctrl_i_work_inside_the_text(app: Page) -> None:
    open_new_note(app)
    ta = textarea(app)
    ta.fill("one two")
    select(ta, 0, 3)
    ta.press("ControlOrMeta+b")
    expect(ta).to_have_value("**one** two")
    ta.fill("x")
    select(ta, 0, 1)
    ta.press("ControlOrMeta+i")
    expect(ta).to_have_value("*x*")


def test_undo_reverts_a_toolbar_edit(app: Page) -> None:
    open_new_note(app)
    ta = textarea(app)
    ta.press_sequentially("alfa beta")  # typed, so the browser has an undo history
    select(ta, 0, 4)
    tool(app, "editor_bold").click()
    expect(ta).to_have_value("**alfa** beta")
    ta.press("ControlOrMeta+z")
    expect(ta).to_have_value("alfa beta")


@pytest.mark.parametrize(
    ("tool_key", "text", "start", "end", "expected"),
    [
        ("editor_strike", "a b", 0, 1, "~~a~~ b"),
        ("editor_h2", "Tytul", 0, 0, "## Tytul"),
        ("editor_h3", "## Tytul", 0, 0, "### Tytul"),
        ("editor_ul", "a\nb", 0, 3, "- a\n- b"),
        ("editor_ol", "a\nb", 0, 3, "1. a\n2. b"),
        ("editor_quote", "cytat", 0, 5, "> cytat"),
        ("editor_code", "uzyj ls teraz", 5, 7, "uzyj `ls` teraz"),
        ("editor_code", "a\nb", 0, 3, "```\na\nb\n```"),
        ("editor_link", "docs", 0, 4, "[docs](https://)"),
    ],
    ids=[
        "strike",
        "h2",
        "h3-replaces-h2",
        "bullets",
        "numbers",
        "quote",
        "inline-code",
        "fenced-code",
        "link",
    ],
)
def test_each_button_inserts_its_markdown(
    app: Page, tool_key: str, text: str, start: int, end: int, expected: str
) -> None:
    open_new_note(app)
    ta = textarea(app)
    ta.fill(text)
    select(ta, start, end)
    tool(app, tool_key).click()
    expect(ta).to_have_value(expected)


def test_the_table_button_inserts_a_two_by_two_table(app: Page) -> None:
    open_new_note(app)
    tool(app, "editor_table").click()
    expect(textarea(app)).to_have_value(
        f"| {T['editor_col1']} | {T['editor_col2']} |\n| --- | --- |\n| {T['editor_cell']} | {T['editor_cell']} |"
    )


def test_the_callout_menu_offers_six_kinds_and_inserts_the_chosen_one(
    app: Page,
) -> None:
    open_new_note(app)
    ta = textarea(app)
    tool(app, "editor_callout").click()
    menu = app.get_by_role("menu")
    expect(menu).to_be_visible()
    for kind in ("info", "tip", "warning", "important", "success", "note"):
        expect(
            menu.get_by_role("menuitem", name=T[f"callout_{kind}"], exact=True)
        ).to_be_visible()

    menu.get_by_role("menuitem", name=T["callout_tip"], exact=True).focus()
    app.keyboard.press("Escape")  # closes only the menu: the form (and its text) stay
    expect(menu).to_be_hidden()
    expect(ta).to_be_visible()

    tool(app, "editor_callout").click()
    menu.get_by_role("menuitem", name=T["callout_warning"], exact=True).click()
    expect(menu).to_be_hidden()
    expect(ta).to_have_value(f"> [!WARNING]\n> {T['editor_ph_text']}")


def test_a_click_outside_closes_the_callout_menu(app: Page) -> None:
    open_new_note(app)
    tool(app, "editor_callout").click()
    expect(app.get_by_role("menu")).to_be_visible()
    app.get_by_text(T["label_title"], exact=True).first.click()
    expect(app.get_by_role("menu")).to_be_hidden()


def test_the_preview_renders_the_note_the_way_the_reader_will(app: Page) -> None:
    open_new_note(app)
    ta = textarea(app)
    ta.fill(MARKDOWN)
    app.get_by_role("tab", name=T["editor_preview"]).click()

    preview = app.locator("#detail .edpreview")
    expect(preview).to_be_visible()
    expect(ta).to_be_hidden()
    expect(
        app.locator("#detail .edtools")
    ).to_be_hidden()  # nothing to format in the preview
    expect(preview.get_by_role("heading", name="Tytuł", level=1)).to_be_visible()
    expect(preview.get_by_role("heading", name="Sekcja", level=2)).to_be_visible()
    expect(preview.get_by_role("listitem")).to_have_count(2)
    expect(preview.locator(".callout.tip")).to_contain_text("wskazówka")
    expect(preview.locator(".codeblock .codelang")).to_have_text("Python")
    expect(preview.get_by_role("table")).to_be_visible()
    expect(preview.locator("strong")).to_have_text("gruby")
    expect(preview).to_contain_text(
        "<b>surowy</b>"
    )  # raw HTML is shown as text, never run
    expect(preview.locator("b")).to_have_count(0)

    app.get_by_role("tab", name=T["editor_write"]).click()
    expect(ta).to_be_visible()
    expect(ta).to_have_value(MARKDOWN)  # going back changes nothing
    expect(ta).to_be_focused()


def test_an_empty_note_previews_as_a_hint(app: Page) -> None:
    open_new_note(app)
    app.get_by_role("tab", name=T["editor_preview"]).click()
    expect(app.get_by_text(T["editor_empty_preview"])).to_be_visible()


def test_the_saved_note_renders_like_the_preview(app: Page) -> None:
    title = unique("Markdown")
    open_new_note(app)
    app.get_by_placeholder(T["label_title"]).fill(title)
    textarea(app).fill(MARKDOWN.replace("<b>surowy</b> ", ""))
    app.get_by_role("button", name=T["save"], exact=True).click()
    detail_title(app, title).wait_for()

    article = app.locator("#detail article.md")
    expect(article.get_by_role("heading", name="Sekcja", level=2)).to_be_visible()
    expect(article.locator(".callout.tip")).to_be_visible()
    expect(article.locator(".codeblock .codelang")).to_have_text("Python")
    expect(article.get_by_role("table")).to_be_visible()
    expect(article.locator("strong")).to_have_text("gruby")
    expect(
        app.get_by_role("button", name=re.compile(re.escape(title))).first
    ).to_be_visible()
