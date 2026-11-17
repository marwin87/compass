"""The login page (served at `/login`): a small standalone page that shares the base styles, the tab
icon and the language switch with the rest of the UI. The only thing it needs from the server is the
language and, after a wrong password, the error text."""

import html

from compass.ui.i18n import LANGS
from compass.ui.page import COMMON_CSS, FAVICON_LINK, LANG_SWITCH_JS, fill

LOGIN_TEMPLATE = (
    '<!doctype html><html lang="[[lang]]"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    "<title>[[login_title]]</title>"
    + FAVICON_LINK
    + "<style>"
    + COMMON_CSS
    + "</style></head><body>"
    '<div class="login"><div style="width:min(380px,100%)">'
    '<form class="card form" method="post" action="/login">'
    '<div class="logo"><div class="dot">🧭</div>Compass</div>'
    '<p class="muted">[[login_intro]]</p>'
    '<input type="password" name="password" placeholder="[[password_ph]]" autofocus required>'
    '<div class="err"><!--error--></div>'
    '<button class="btn primary">[[login_btn]]</button></form>'
    '<div class="langs" role="group" aria-label="[[lang_label]]" '
    'style="justify-content:center;margin-top:14px"><!--langs--></div></div></div>'
    "<script>" + LANG_SWITCH_JS + "</script></body></html>"
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
