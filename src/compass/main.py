from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware

from compass import api, auth, config
from compass.db import connect
from compass.page import INDEX_HTML

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
    # Added last = outermost: the session must be loaded before the guard runs.
    app.middleware("http")(auth.guard)
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.secret_key(),
        max_age=SESSION_MAX_AGE,
        same_site="lax",
    )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
