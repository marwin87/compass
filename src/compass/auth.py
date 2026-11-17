import hmac
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from compass import config

PUBLIC_PATHS = {"/login", "/health"}

router = APIRouter()


def _login_page(error: str = "") -> str:
    message = f"<p>{error}</p>" if error else ""
    return (
        "<!doctype html><title>Compass - login</title><h1>Compass</h1>"
        f"{message}"
        '<form method="post" action="/login">'
        '<label>Password <input type="password" name="password" autofocus required></label> '
        "<button>Log in</button></form>"
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
    return HTMLResponse(_login_page("Wrong password."), status_code=401)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
