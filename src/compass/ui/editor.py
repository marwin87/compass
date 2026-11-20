"""The Markdown helper for the note forms: a toolbar over the plain textarea and a preview tab.

The note stays plain text in the textarea. The toolbar only edits that text: each button is a pure
function (`EDITOR_PURE_JS`, no DOM, tested in Node) that turns the text and the selection into one
replacement (`{from, to, insert, selFrom, selTo}`). The DOM part (`EDITOR_UI_JS`) applies it with
`execCommand("insertText")`, which keeps the browser's undo history (`setRangeText` is the fallback),
and draws the preview with the same parser and renderer as the note reader, so the preview always
looks like the saved note. No library, no HTML strings, no external request.
"""

from compass.ui import asset

EDITOR_PURE_JS = asset("editor.pure.js")

EDITOR_UI_JS = asset("editor.ui.js")

EDITOR_CSS = asset("editor.css")
