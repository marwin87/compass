import hmac
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from compass import config
from compass.page import COMMON_CSS

PUBLIC_PATHS = {"/login", "/health"}

router = APIRouter()


def _login_page(error: str = "") -> str:
    return (
        '<!doctype html><html lang="pl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Compass - logowanie</title><style>{COMMON_CSS}</style></head><body>"
        '<div class="login"><form class="card form" method="post" action="/login">'
        '<div class="logo"><div class="dot">🧭</div>Compass</div>'
        '<p class="muted">Zaloguj się hasłem, żeby zobaczyć swoje notatki.</p>'
        '<input type="password" name="password" placeholder="Hasło" autofocus required>'
        f'<div class="err">{error}</div>'
        '<button class="btn primary">Zaloguj</button></form></div></body></html>'
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
def login_form() -> str:
    return _login_page()


@router.post("/login", response_model=None)
def login(request: Request, password: Annotated[str, Form()]) -> Response:
    if hmac.compare_digest(password.encode(), config.password().encode()):
        request.session["auth"] = True
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(_login_page("Nieprawidłowe hasło."), status_code=401)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
