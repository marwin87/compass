"""The login page (served at `/login`): a small standalone page that shares the base styles, the tab
icon and the language switch with the rest of the UI. The only thing it needs from the server is the
language and, after a wrong password, the error text."""

import html

from compass.ui import asset
from compass.ui.i18n import LANGS
from compass.ui.page import COMMON_CSS, FAVICON_LINK, LANG_SWITCH_JS, fill

# The same compass icon as the notes page (ICONS.compass in core.py, size 22), drawn inline: this page loads no core script.
COMPASS = (
    '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>'
)
EYE = (
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
)
EYE_OPEN = (
    EYE
    + '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>'
)
EYE_OFF = (
    EYE
    + '<path d="M10.7 5.1A10.4 10.4 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-2.6 3.4M6.6 6.6A17 17 0 0 0 2 12s3.6 7 10 7a10 10 0 0 0 5.4-1.6"/>'
    '<path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/><path d="m2 2 20 20"/></svg>'
)
LOGIN_CSS = asset("login.css")
PASSWORD_JS = asset("password.js")

LOGIN_TEMPLATE = (
    asset("login.html")
    .replace("<!--FAVICON-->", FAVICON_LINK)
    .replace("/*COMMON_CSS*/", COMMON_CSS)
    .replace("/*LOGIN_CSS*/", LOGIN_CSS)
    .replace("<!--COMPASS-->", COMPASS)
    .replace("<!--EYE_OPEN-->", EYE_OPEN)
    .replace("<!--EYE_OFF-->", EYE_OFF.replace("<svg", "<svg hidden", 1))
    .replace("/*LANG_SWITCH_JS*/", LANG_SWITCH_JS)
    .replace("/*PASSWORD_JS*/", PASSWORD_JS)
)


def render_login(lang: str, error: str = "") -> str:
    buttons = "".join(
        f'<button type="button" class="btn icon{" on" if code == lang else ""}" '
        f'data-lang="{code}">{code.upper()}</button>'
        for code in LANGS
    )
    return (
        fill(LOGIN_TEMPLATE, lang)
        .replace("<!--error-->", html.escape(error))
        .replace("<!--langs-->", buttons)
    )
