"""The chat with the notes (AI): its panel in the detail column, embedded into the notes page.

One panel lives for the whole page session (the page keeps it, so opening a source note and coming back
loses nothing). A conversation is created on the first question, so no empty ones are saved. Rules:
`docs/STYLE_GUIDE.md` section 9.
"""

from compass.ui import asset

CHAT_CSS = asset("chat.css")

CHAT_JS = asset("chat.js")
