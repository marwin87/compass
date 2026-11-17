import hmac
import html
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from compass import config
from compass.i18n import COOKIE, LANGS, STRINGS, pick_lang
from compass.page import COMMON_CSS, FAVICON_LINK, LANG_SWITCH_JS, fill

PUBLIC_PATHS = {"/login", "/health"}

router = APIRouter()


def _lang(request: Request) -> str:
    return pick_lang(
        request.cookies.get(COOKIE), request.headers.get("accept-language")
    )


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


def _login_page(lang: str, error: str = "") -> str:
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


async def guard(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.url.path in PUBLIC_PATHS or request.session.get("auth"):
        return await call_next(request)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    return RedirectResponse("/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request) -> str:
    return _login_page(_lang(request))


@router.post("/login", response_model=None)
def login(request: Request, password: Annotated[str, Form()]) -> Response:
    if hmac.compare_digest(password.encode(), config.password().encode()):
        request.session["auth"] = True
        return RedirectResponse("/", status_code=303)
    lang = _lang(request)
    return HTMLResponse(_login_page(lang, STRINGS[lang]["wrong_pw"]), status_code=401)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
