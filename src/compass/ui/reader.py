"""The note reader: a safe Markdown renderer for note bodies, plus its styles.

Notes are stored as plain text and never rewritten. They are *displayed* through a small Markdown
parser (`READER_PURE_JS`, no DOM, unit-tested in `tests/ui/test_reader.py`) and a DOM builder
(`READER_UI_JS`). Nothing here produces HTML strings: every node is created with DOM calls, links
are limited to safe schemes, and raw HTML in a note is shown as text. Single line breaks are kept,
so old plain-text notes look the way they always did.
"""

from compass.ui import asset

READER_PURE_JS = asset("reader.pure.js")

READER_UI_JS = asset("reader.ui.js")

READER_CSS = asset("reader.css")
