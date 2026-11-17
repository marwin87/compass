"""Unit tests for the Markdown parser and the syntax highlighter of the note reader.

They are plain JavaScript (`compass.reader.READER_PURE_JS`, no DOM), so the tests run it in Node. Without Node
they are skipped locally and fail in CI.
"""

import json
import os
import shutil
import subprocess
from typing import Any

import pytest

from compass.ui.reader import READER_PURE_JS

# Locally these tests are skipped without Node; in CI (GitHub Actions sets CI=true) a missing Node must fail
# the build, so the parser tests can never be skipped silently there.
pytestmark = pytest.mark.skipif(
    shutil.which("node") is None and not os.environ.get("CI"),
    reason="node is not installed",
)


def js(expression: str, arg: Any = None) -> Any:
    """Evaluate `expression` (with `A` bound to `arg`) next to the reader code; returns the JSON result."""
    code = (
        READER_PURE_JS
        + f"\nconst A = JSON.parse(process.argv[1]); console.log(JSON.stringify({expression}));"
    )
    run = subprocess.run(
        ["node", "-e", code, json.dumps(arg)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def types(text: str) -> list[str]:
    result: list[str] = js("mdParse(A).map((b) => b.t)", text)
    return result


def plain(nodes: list[dict[str, Any]]) -> str:
    return "".join(
        n.get("v", "\n" if n["t"] == "br" else plain(n.get("c", []))) for n in nodes
    )


def test_plain_notes_keep_their_text_and_line_breaks() -> None:
    old = (
        'Pierwsza linia\nDruga linia, z przecinkiem; i "cudzysłowem" 🙂\n\nNowy akapit'
    )
    blocks = js("mdParse(A)", old)
    assert [b["t"] for b in blocks] == ["p", "p"]
    assert (
        plain(blocks[0]["c"])
        == 'Pierwsza linia\nDruga linia, z przecinkiem; i "cudzysłowem" 🙂'
    )
    assert plain(blocks[1]["c"]) == "Nowy akapit"


def test_empty_and_blank_notes_are_fine() -> None:
    assert js("mdParse(A)", "") == []
    assert js("mdParse(A)", "\n\n   \n") == []


def test_windows_line_endings_and_tabs() -> None:
    assert types("a\r\nb\r\n\r\nc") == ["p", "p"]
    assert types("-\tone\n-\ttwo") == ["ul"]


def test_headings_levels_and_the_space_rule() -> None:
    blocks = js(
        "mdParse(A)", "# Jeden\n## Dwa ##\n###### Sześć\n#nietytuł\n####### siedem"
    )
    assert [(b["t"], b.get("level")) for b in blocks[:3]] == [
        ("h", 1),
        ("h", 2),
        ("h", 6),
    ]
    assert plain(blocks[1]["c"]) == "Dwa"
    assert blocks[3]["t"] == "p" and "#nietytuł" in plain(
        blocks[3]["c"]
    )  # no space: not a heading


def test_lists_ordered_unordered_and_nested() -> None:
    text = "- a\n- b\n  - b1\n  - b2\n    - b2x\n- c\n\n1. jeden\n2. dwa\n3. trzy"
    blocks = js("mdParse(A)", text)
    assert [b["t"] for b in blocks] == ["ul", "ol"]
    items = blocks[0]["items"]
    assert len(items) == 3
    nested = items[1]["c"][1]
    assert nested["t"] == "ul" and len(nested["items"]) == 2
    assert nested["items"][1]["c"][1]["t"] == "ul"  # third level
    assert blocks[1]["start"] == 1 and len(blocks[1]["items"]) == 3


def test_a_loose_ordered_list_stays_one_list_and_keeps_its_start() -> None:
    blocks = js("mdParse(A)", "3. trzy\n\n4. cztery\n\n5. pięć")
    assert [b["t"] for b in blocks] == ["ol"]
    assert blocks[0]["start"] == 3 and len(blocks[0]["items"]) == 3


def test_list_item_continuation_lines() -> None:
    blocks = js("mdParse(A)", "- pierwsza linia\n  druga linia\n- następna")
    assert len(blocks[0]["items"]) == 2
    assert plain(blocks[0]["items"][0]["c"][0]["c"]) == "pierwsza linia\ndruga linia"


def test_a_list_can_follow_a_paragraph_without_a_blank_line() -> None:
    assert types("Składniki:\n- mąka\n- mleko") == ["p", "ul"]
    assert types("Kroki:\n1. wymieszaj\n2. smaż") == ["p", "ol"]
    assert types("Rok:\n2026. było dobrze") == ["p"]  # only "1." interrupts a paragraph


def test_fenced_code_keeps_everything_and_reads_the_language() -> None:
    text = "przed\n```python\ndef f():\n    # **nie pogrubiaj**\n    return 1\n```\npo"
    blocks = js("mdParse(A)", text)
    assert [b["t"] for b in blocks] == ["p", "code", "p"]
    assert blocks[1]["lang"] == "python"
    assert blocks[1]["text"] == "def f():\n    # **nie pogrubiaj**\n    return 1"


def test_an_unclosed_fence_runs_to_the_end_and_tilde_fences_work() -> None:
    blocks = js("mdParse(A)", "```\nx = 1\ny = 2")
    assert blocks == [{"t": "code", "lang": "", "text": "x = 1\ny = 2"}]
    assert js("mdParse(A)[0].text", "~~~sql\nselect 1\n~~~") == "select 1"


def test_tables_with_alignment_and_escaped_pipes() -> None:
    text = "| Nazwa | Cena | Opis |\n|:--|--:|:-:|\n| a | 1 | x \\| y |\n| b | 2 |"
    table = js("mdParse(A)[0]", text)
    assert table["t"] == "table" and table["align"] == ["left", "right", "center"]
    assert [plain(c) for c in table["head"]] == ["Nazwa", "Cena", "Opis"]
    assert [plain(c) for c in table["rows"][0]] == ["a", "1", "x | y"]
    assert [plain(c) for c in table["rows"][1]] == [
        "b",
        "2",
        "",
    ]  # short rows are padded


def test_a_line_with_a_pipe_is_not_a_table_without_a_separator() -> None:
    assert types("a | b\nc | d") == ["p"]


def test_blockquote_and_callouts() -> None:
    blocks = js(
        "mdParse(A)",
        "> zwykły cytat\n> druga linia\n\n> [!TIP] Szybka wskazówka\n> więcej tekstu\n\n> [!warning]\n> uwaga\n\n> [!CAUTION]\n> to samo co warning",
    )
    assert [b["t"] for b in blocks] == ["quote", "callout", "callout", "callout"]
    assert blocks[1]["kind"] == "tip" and plain(blocks[1]["c"][0]["c"]).startswith(
        "Szybka wskazówka"
    )
    assert blocks[2]["kind"] == "warning" and blocks[3]["kind"] == "warning"


@pytest.mark.parametrize(
    "kind", ["note", "info", "tip", "warning", "important", "success"]
)
def test_every_callout_kind_is_recognised(kind: str) -> None:
    assert js("mdParse(A)[0].kind", f"> [!{kind.upper()}]\n> tekst") == kind


def test_horizontal_rules() -> None:
    assert types("a\n\n---\n\nb") == ["p", "hr", "p"]
    assert (
        types("***") == ["hr"] and types("- - -") == ["hr"] and types("___") == ["hr"]
    )


def test_inline_formatting() -> None:
    nodes = js("mdInline(A)", "**gruby** *kursywa* _też_ ~~skreślone~~ `kod`")
    kinds = [n["t"] for n in nodes if n["t"] != "text"]
    assert kinds == ["strong", "em", "em", "del", "code"]


def test_inline_nesting_and_code_is_literal() -> None:
    nodes = js("mdInline(A)", "**a *b* c** i `**nie**`")
    assert nodes[0]["t"] == "strong" and [n["t"] for n in nodes[0]["c"]] == [
        "text",
        "em",
        "text",
    ]
    assert nodes[-1] == {"t": "code", "v": "**nie**"}


def test_snake_case_and_math_are_not_italic() -> None:
    assert [n["t"] for n in js("mdInline(A)", "zmienna_o_nazwie i 2 * 3 * 4")] == [
        "text"
    ]


def test_escapes() -> None:
    assert plain(js("mdInline(A)", "\\*nie\\* \\# \\`")) == "*nie* # `"


def test_links_are_limited_to_safe_schemes() -> None:
    safe = js(
        "mdInline(A)",
        "[ok](https://example.com) [mail](mailto:a@b.pl) [loc](/x) [kotwica](#sekcja)",
    )
    assert [n["href"] for n in safe if n["t"] == "link"] == [
        "https://example.com",
        "mailto:a@b.pl",
        "/x",
        "#sekcja",
    ]
    for bad in ("javascript:alert(1)", "data:text/html,x", "vbscript:x", "example.com"):
        nodes = js("mdInline(A)", f"[klik]({bad})")
        assert all(n["t"] == "text" for n in nodes), bad  # shown as text, never a link


def test_bare_urls_become_links_without_trailing_punctuation() -> None:
    nodes = js("mdInline(A)", "Zobacz https://example.com/a?b=1. Koniec")
    link = next(n for n in nodes if n["t"] == "link")
    assert link["href"] == "https://example.com/a?b=1"


def test_raw_html_is_text_not_markup() -> None:
    blocks = js(
        "mdParse(A)", "<script>alert(1)</script> <img src=x onerror=alert(1)> <b>b</b>"
    )
    assert [b["t"] for b in blocks] == ["p"]
    assert all(n["t"] == "text" for n in blocks[0]["c"])
    assert "<script>" in plain(blocks[0]["c"])


def test_images_are_not_loaded() -> None:
    nodes = js("mdInline(A)", "![alt](https://example.com/x.png)")
    assert all(
        n["t"] in ("text", "link") for n in nodes
    )  # there is no image node at all


def test_mixed_document_has_the_expected_shape() -> None:
    doc = "# Tytuł\n\nWstęp.\n\n## Sekcja\n\n- a\n- b\n\n```js\nlet x = 1\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n> [!NOTE]\n> koniec\n\n---"
    assert types(doc) == ["h", "p", "h", "ul", "code", "table", "callout", "hr"]


# --- syntax highlighting


def hl(lang: str, code: str) -> list[list[str]]:
    result: list[list[str]] = js("mdHighlight(A[1], A[0])", [lang, code])
    return result


def classes(tokens: list[list[str]]) -> set[str]:
    return {cls for cls, _ in tokens if cls}


def test_highlighting_never_changes_the_code() -> None:
    samples = {
        "python": 'def f(x):\n    return "a" + str(x)  # ok\n',
        "js": "const a = `x ${1}`; // c\nfunction g() { return /* y */ 2 }\n",
        "sql": "SELECT a, COUNT(*) FROM t WHERE x = 'y' -- c\n",
        "json": '{"a": [1, 2.5, true, null]}',
        "bash": 'echo "$HOME" # c\nif [ -f x ]; then ls; fi\n',
        "yaml": "a: 1\nb: [x, y] # c\n",
        "css": "a { color: #fff; margin: 0 } /* c */",
        "html": '<div class="a">x</div><!-- c -->',
    }
    for lang, code in samples.items():
        assert "".join(t for _, t in hl(lang, code)) == code, lang


def test_python_tokens() -> None:
    tokens = hl("python", 'def f(x):\n    return "a"  # c\n')
    assert {"tk-kw", "tk-str", "tk-com", "tk-fn"} <= classes(tokens)


def test_sql_keywords_are_case_insensitive() -> None:
    assert classes(hl("sql", "select * from t")) == {"tk-kw"}
    assert ["tk-kw", "SeLeCt"] in hl("sql", "SeLeCt 1")  # the text keeps its case


def test_words_inside_identifiers_are_not_keywords() -> None:
    assert classes(hl("js", "const classify = format_x")) <= {"tk-kw"}
    assert ["tk-kw", "class"] not in hl("js", "classify")


def test_unknown_language_and_huge_code_are_left_plain() -> None:
    assert hl("", "anything") == [["", "anything"]]
    assert js("mdHighlight(A, 'js')", "x" * 30001) == [["", "x" * 30001]]


def test_language_names_and_aliases() -> None:
    for alias, lang in {
        "py": "python",
        "ts": "js",
        "sh": "bash",
        "yml": "yaml",
        "postgres": "sql",
        "xml": "html",
    }.items():
        assert js("hlLang(A)", alias) == lang
    assert js("hlLang(A)", "klingon") == ""


@pytest.mark.parametrize(
    ("code", "lang"),
    [
        ('{"a": 1, "b": [1, 2]}', "json"),
        ("SELECT id, name FROM users WHERE id = 1;", "sql"),
        ("def add(a, b):\n    return a + b", "python"),
        ("const add = (a, b) => a + b;\nconsole.log(add(1, 2))", "js"),
        ("$ docker compose up --build", "bash"),
        ("<div>\n  <p>hi</p>\n</div>", "html"),
        ("name: compass\nport: 8011", "yaml"),
        ("zwykły tekst bez kodu", ""),
    ],
)
def test_language_detection(code: str, lang: str) -> None:
    assert js("hlDetect(A)", code) == lang


def test_plain_text_is_not_mistaken_for_json() -> None:
    assert js("hlDetect(A)", "[1] to jest odnośnik, a nie JSON") == ""


def test_the_demo_markdown_notes_show_what_the_reader_can_do() -> None:
    from pathlib import Path

    demo = json.loads(
        (Path(__file__).resolve().parents[2] / "demo" / "compass-demo.json").read_text(
            encoding="utf-8"
        )
    )
    by_title = {n["title"]: n["body"] for n in demo["notes"]}
    guide = js("mdParse(A)", by_title["Przewodnik: Markdown w Compass"])
    kinds = {b["kind"] for b in guide if b["t"] == "callout"}
    assert kinds == {"info", "tip", "warning", "important", "success", "note"}
    assert {"table", "code", "hr", "quote", "ul", "ol"} <= {b["t"] for b in guide}
    long_note = js("mdParse(A)", by_title["B-drzewo od środka (długa notatka)"])
    assert (
        sum(1 for b in long_note if b["t"] == "h" and b["level"] in (2, 3)) >= 3
    )  # gets a table of contents
    old = [n for n in demo["notes"] if n["id"] <= 21]
    assert (
        len(old) == 21
    )  # the original plain-text notes are still there as a compatibility check
