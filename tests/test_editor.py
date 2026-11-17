"""Unit tests for the Markdown editing helpers of the note forms.

The helpers are plain JavaScript (`compass.editor.EDITOR_PURE_JS`, no DOM) and are run in Node, next to the
reader's parser (`READER_PURE_JS`) to prove that what the toolbar inserts is what the reader understands.
Without Node the tests are skipped locally and fail in CI.
"""

import json
import os
import shutil
import subprocess
from typing import Any

import pytest

from compass.editor import EDITOR_PURE_JS
from compass.reader import READER_PURE_JS

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None and not os.environ.get("CI"),
    reason="node is not installed",
)

# ap(text, edit) -> {text, sel}: the text after the replacement and what is selected in it
PRELUDE = """
const ap = (t, r) => { const n = t.slice(0, r.from) + r.insert + t.slice(r.to); return {text: n, sel: n.slice(r.selFrom, r.selTo)}; };
const A = JSON.parse(process.argv[1]);
"""


def js(expression: str, arg: Any = None) -> Any:
    code = (
        READER_PURE_JS
        + EDITOR_PURE_JS
        + PRELUDE
        + f"\nconsole.log(JSON.stringify({expression}));"
    )
    run = subprocess.run(
        ["node", "-e", code, json.dumps(arg)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def wrap(
    text: str, a: int, b: int, before: str = "**", after: str | None = None
) -> dict[str, str]:
    result: dict[str, str] = js(
        "ap(A[0], edWrap(A[0], A[1], A[2], A[3], A[4], 'text'))",
        [text, a, b, before, before if after is None else after],
    )
    return result


def lines(text: str, a: int, b: int, kind: str) -> dict[str, str]:
    result: dict[str, str] = js(
        "ap(A[0], edLines(A[0], A[1], A[2], A[3]))", [text, a, b, kind]
    )
    return result


# --- bold, italic, strike, inline code


def test_wrapping_a_selection() -> None:
    assert wrap("x abc y", 2, 5) == {"text": "x **abc** y", "sel": "abc"}


def test_wrapping_nothing_inserts_a_placeholder_that_is_selected() -> None:
    assert wrap("ab", 1, 1) == {"text": "a**text**b", "sel": "text"}


def test_wrapping_twice_unwraps_again() -> None:
    once = wrap("x abc y", 2, 5)
    again = wrap(once["text"], 4, 7)
    assert again == {"text": "x abc y", "sel": "abc"}


def test_unwrapping_when_the_selection_includes_the_markers() -> None:
    assert wrap("x **abc** y", 2, 9) == {"text": "x abc y", "sel": "abc"}


def test_italic_inside_bold_does_not_break_the_bold() -> None:
    assert wrap("**abc**", 2, 5, "*") == {"text": "***abc***", "sel": "abc"}


def test_italic_unwraps_its_own_markers() -> None:
    assert wrap("*abc*", 1, 4, "*") == {"text": "abc", "sel": "abc"}
    assert wrap("*abc*", 0, 5, "*") == {"text": "abc", "sel": "abc"}


def test_strikethrough() -> None:
    assert wrap("a b", 0, 1, "~~") == {"text": "~~a~~ b", "sel": "a"}


def test_wrapping_at_the_very_start_and_end() -> None:
    assert wrap("abc", 0, 3) == {"text": "**abc**", "sel": "abc"}
    assert wrap("", 0, 0) == {"text": "**text**", "sel": "text"}


# --- line markers: headings, lists, quotes


def test_heading_toggles_and_replaces_other_levels() -> None:
    assert lines("Title", 0, 0, "h2")["text"] == "## Title"
    assert lines("## Title", 3, 3, "h2")["text"] == "Title"
    assert lines("### Title", 0, 0, "h2")["text"] == "## Title"
    assert lines("# Title", 0, 0, "h3")["text"] == "### Title"
    assert lines("", 0, 0, "h2")["text"] == "## "


def test_a_cursor_in_the_middle_of_a_line_marks_the_whole_line() -> None:
    assert (
        lines("one\ntwo words\nthree", 7, 7, "h2")["text"] == "one\n## two words\nthree"
    )


def test_bullets_on_several_lines_keep_blank_lines() -> None:
    assert lines("a\n\nb", 0, 4, "ul")["text"] == "- a\n\n- b"
    assert lines("- a\n\n- b", 0, 8, "ul")["text"] == "a\n\nb"


def test_numbering_counts_only_the_filled_lines() -> None:
    assert lines("a\nb\n\nc", 0, 6, "ol")["text"] == "1. a\n2. b\n\n3. c"


def test_switching_between_bullets_and_numbers() -> None:
    assert lines("- a\n- b", 0, 7, "ol")["text"] == "1. a\n2. b"
    assert lines("1. a\n2. b", 0, 9, "ul")["text"] == "- a\n- b"
    assert lines("1. a\n2. b", 0, 9, "ol")["text"] == "a\nb"


def test_quote_toggles() -> None:
    assert lines("a\nb", 0, 3, "quote")["text"] == "> a\n> b"
    assert lines("> a\n> b", 0, 7, "quote")["text"] == "a\nb"


def test_a_selection_ending_at_a_line_start_does_not_touch_that_line() -> None:
    assert (
        lines("a\nb\nc", 0, 4, "ul")["text"] == "- a\n- b\nc"
    )  # selection "a\nb\n" ends where "c" begins


def test_the_result_selects_the_changed_lines() -> None:
    assert lines("one\ntwo\nthree", 4, 7, "ul") == {
        "text": "one\n- two\nthree",
        "sel": "- two",
    }


def test_a_first_line_that_is_empty() -> None:
    assert lines("\nabc", 0, 0, "ul")["text"] == "- \nabc"


# --- code


def code(text: str, a: int, b: int) -> dict[str, str]:
    result: dict[str, str] = js(
        "ap(A[0], edCode(A[0], A[1], A[2], 'code'))", [text, a, b]
    )
    return result


def test_inline_code_for_one_line() -> None:
    assert code("run ls now", 4, 6) == {"text": "run `ls` now", "sel": "ls"}
    assert code("x", 1, 1) == {"text": "x`code`", "sel": "code"}


def test_a_fenced_block_for_several_lines() -> None:
    assert code("a\nb\nc", 0, 3) == {"text": "```\na\nb\n```\nc", "sel": "a\nb"}


def test_a_fenced_block_is_removed_when_selected_again() -> None:
    fenced = "```\na\nb\n```"
    assert code(fenced, 0, len(fenced)) == {"text": "a\nb", "sel": "a\nb"}


# --- link


def link(text: str, a: int, b: int) -> dict[str, str]:
    result: dict[str, str] = js(
        "ap(A[0], edLink(A[0], A[1], A[2], 'link text'))", [text, a, b]
    )
    return result


def test_link_without_a_selection_selects_the_label() -> None:
    assert link("", 0, 0) == {"text": "[link text](https://)", "sel": "link text"}


def test_link_with_a_selection_selects_the_address_to_type_over() -> None:
    assert link("see docs", 4, 8) == {"text": "see [docs](https://)", "sel": "https://"}


def test_a_selected_address_becomes_the_target() -> None:
    assert link("go https://example.com now", 3, 22) == {
        "text": "go [link text](https://example.com) now",
        "sel": "link text",
    }


# --- blocks: table and callout


def table(text: str, a: int, b: int) -> dict[str, str]:
    result: dict[str, str] = js(
        "ap(A[0], edTable(A[0], A[1], A[2], {col1: 'Col 1', col2: 'Col 2', cell: 'cell'}))",
        [text, a, b],
    )
    return result


def test_a_table_in_an_empty_note() -> None:
    result = table("", 0, 0)
    assert result["text"] == "| Col 1 | Col 2 |\n| --- | --- |\n| cell | cell |"
    assert result["sel"] == "Col 1"


def test_a_table_is_separated_from_the_text_around_it() -> None:
    assert table("intro", 5, 5)["text"].startswith("intro\n\n| Col 1")
    assert table("intro\n", 6, 6)["text"].startswith("intro\n\n| Col 1")
    assert table("intro\n\n", 7, 7)["text"].startswith("intro\n\n| Col 1")
    result = table("a\n\nrest", 3, 3)["text"]
    assert result.endswith("| cell | cell |\n\nrest") and result.startswith(
        "a\n\n| Col 1"
    )


def callout(text: str, a: int, b: int, kind: str = "tip") -> dict[str, str]:
    result: dict[str, str] = js(
        "ap(A[0], edCallout(A[0], A[1], A[2], A[3], 'text'))", [text, a, b, kind]
    )
    return result


def test_an_empty_callout_has_a_selected_body_placeholder() -> None:
    assert callout("", 0, 0) == {"text": "> [!TIP]\n> text", "sel": "text"}
    assert callout("", 0, 0, "important")["text"].startswith("> [!IMPORTANT]\n")


def test_a_callout_wraps_the_selected_lines() -> None:
    assert callout("keep\nthis\nthat", 5, 9, "warning") == {
        "text": "keep\n\n> [!WARNING]\n> this\n\nthat",
        "sel": "> this",
    }


@pytest.mark.parametrize(
    "kind", ["note", "info", "tip", "warning", "important", "success"]
)
def test_what_the_toolbar_inserts_is_understood_by_the_reader(kind: str) -> None:
    text = callout("before", 6, 6, kind)["text"]
    blocks = js("mdParse(A)", text)
    assert [b["t"] for b in blocks] == ["p", "callout"] and blocks[1]["kind"] == kind


def test_the_table_and_the_lists_are_understood_by_the_reader() -> None:
    assert js("mdParse(A).map((b) => b.t)", table("intro", 5, 5)["text"]) == [
        "p",
        "table",
    ]
    assert js("mdParse(A).map((b) => b.t)", lines("a\nb", 0, 3, "ol")["text"]) == ["ol"]
    assert js("mdParse(A).map((b) => b.t)", lines("a\nb", 0, 3, "quote")["text"]) == [
        "quote"
    ]
    assert js("mdParse(A).map((b) => b.t)", lines("T", 0, 1, "h2")["text"]) == ["h"]
    assert js("mdParse(A).map((b) => b.t)", code("a\nb", 0, 3)["text"]) == ["code"]
