"""The HTTP API, one module per resource; `router` is all of them."""

from fastapi import APIRouter

from compass.routes import ai, categories, chats, notes, system, tags, transfer

router = APIRouter()
for part in (
    notes.router,
    tags.router,
    transfer.export_router,
    transfer.import_router,
    categories.router,
    system.settings_router,
    ai.router,
    chats.router,
    system.about_router,
    system.data_router,
):
    router.include_router(part)
