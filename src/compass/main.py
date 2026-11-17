from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from compass.db import connect


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    connect().close()
    yield


app = FastAPI(title="Compass", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return "<!doctype html><title>Compass</title><h1>Compass</h1>"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
