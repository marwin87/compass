import itertools

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from compass import (
    ai,
    api,
    chunks,
    settings,
)

router = APIRouter(prefix="/api/ai")


@router.get("/status")
def ai_status() -> dict[str, object]:
    return ai.status(settings.current())


@router.get("/index")
def index_status() -> dict[str, int]:
    """How many notes the chat's vector index covers (`indexed` of `total`)."""
    return chunks.status(settings.current())


@router.post("/index")
def index_notes() -> StreamingResponse:
    """Embed the notes that are new or changed since the last run, streamed as one JSON line per event
    (`start`, `progress`, `done`, or `error`). Costs model calls, so it only runs when asked."""
    events = chunks.sync(settings.current())
    try:
        first = next(
            events
        )  # AI off / not configured / no embedding model: a plain error
    except ai.AIError as problem:
        raise api.ai_error(problem) from None
    return StreamingResponse(
        api.lines(itertools.chain([first], events)),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store"},
    )


@router.delete("/index", status_code=204)
def clear_index() -> None:
    """Empty the chat's vector index (notes, search and conversations are untouched)."""
    chunks.clear()
