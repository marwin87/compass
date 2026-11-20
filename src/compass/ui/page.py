"""The single notes page (served at `/`) and the CSS shared with the login page.

Built from DOM calls only: note text and tags are inserted with `textContent` / `value`,
never as HTML. The server ranks the results; the highlighting here is cosmetic.
UI text lives in `i18n.py`: `[[key]]` markers are filled in on the server, the script reads the
same strings from the embedded `I18N` object.
"""

import html
import re
from collections.abc import Mapping
from urllib.parse import quote

from compass.ui import asset, core
from compass.ui.chatpanel import CHAT_CSS, CHAT_JS
from compass.ui.editor import EDITOR_CSS, EDITOR_PURE_JS, EDITOR_UI_JS
from compass.ui.i18n import STRINGS
from compass.ui.reader import READER_CSS, READER_PURE_JS, READER_UI_JS

# The tab icon: the logo (compass on the brand gradient) as an inline SVG data URI, so the page
# still makes no external request and needs no extra route.
_FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
    "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
    "<stop offset='0' stop-color='#477bff'/><stop offset='1' stop-color='#765bff'/></linearGradient></defs>"
    "<rect width='32' height='32' rx='8' fill='url(#g)'/>"
    "<g transform='translate(5 5) scale(.917)' fill='none' stroke='white' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='10'/>"
    "<polygon points='16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76'/></g></svg>"
)
FAVICON_LINK = (
    '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,'
    + quote(_FAVICON_SVG, safe="/:='")
    + '">'
)

COMMON_CSS = asset("common.css")
APP_CSS = asset("app.css")

INDEX_HTML = (
    asset("index.html")
    .replace("<!--FAVICON-->", FAVICON_LINK)
    .replace("/*CSS*/", COMMON_CSS + APP_CSS + READER_CSS + EDITOR_CSS + CHAT_CSS)
    .replace("/*APP_JS*/", asset("app.js"))
    .replace("/*CORE*/", core.CORE_JS)
    .replace("/*READER_PURE*/", READER_PURE_JS)
    .replace("/*READER_UI*/", READER_UI_JS)
    .replace("/*EDITOR_PURE*/", EDITOR_PURE_JS)
    .replace("/*EDITOR_UI*/", EDITOR_UI_JS)
    .replace("/*CHAT_UI*/", CHAT_JS)
)

LANG_SWITCH_JS = (
    'document.querySelectorAll("[data-lang]").forEach(function(b){'
    'b.addEventListener("click",function(){document.cookie="lang="+b.dataset.lang+'
    '"; path=/; max-age=31536000; SameSite=Lax";location.reload();});});'
)


def fill(template: str, lang: str) -> str:
    """Replace `[[key]]` markers with the escaped UI strings of `lang` (a missing key is an error)."""
    strings = {**STRINGS[lang], "lang": lang}
    return re.sub(
        r"\[\[(\w+)\]\]",
        lambda m: html.escape(strings[m.group(1)], quote=True),
        template,
    )


def render_index(lang: str, settings: Mapping[str, object] | None = None) -> str:
    return core.inject(fill(INDEX_HTML, lang), lang, settings)
