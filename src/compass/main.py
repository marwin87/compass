from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware

from compass import api, auth, config, settings
from compass.db import connect
from compass.i18n import COOKIE, pick_lang
from compass.page import render_index
from compass.settings_page import render_settings

SESSION_MAX_AGE = 30 * 24 * 3600


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    connect().close()
    yield


def create_app() -> FastAPI:
    config.password()  # fail fast when the password is not configured
    app = FastAPI(title="Compass", lifespan=lifespan)
    app.include_router(auth.router)
    app.include_router(api.router)
    app.include_router(api.tags_router)
    app.include_router(api.export_router)
    app.include_router(api.import_router)
    app.include_router(api.categories_router)
    app.include_router(api.settings_router)
    app.include_router(api.about_router)
    app.include_router(api.data_router)
    # Added last = outermost: the session must be loaded before the guard runs.
    app.middleware("http")(auth.guard)
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.secret_key(),
        max_age=SESSION_MAX_AGE,
        same_site="lax",
    )

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> str:
        lang = pick_lang(
            request.cookies.get(COOKIE), request.headers.get("accept-language")
        )
        return render_index(lang, settings.current())

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request) -> str:
        lang = pick_lang(
            request.cookies.get(COOKIE), request.headers.get("accept-language")
        )
        return render_settings(lang, settings.current())

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
