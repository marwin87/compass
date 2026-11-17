import hmac
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from compass import config
from compass.ui.i18n import COOKIE, STRINGS, pick_lang
from compass.ui.login import render_login

PUBLIC_PATHS = {"/login", "/health"}

router = APIRouter()


def _lang(request: Request) -> str:
    return pick_lang(
        request.cookies.get(COOKIE), request.headers.get("accept-language")
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
    return render_login(_lang(request))


@router.post("/login", response_model=None)
def login(request: Request, password: Annotated[str, Form()]) -> Response:
    if hmac.compare_digest(password.encode(), config.password().encode()):
        request.session["auth"] = True
        return RedirectResponse("/", status_code=303)
    lang = _lang(request)
    return HTMLResponse(render_login(lang, STRINGS[lang]["wrong_pw"]), status_code=401)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
