import json
from datetime import UTC, datetime
from pathlib import PurePath

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from compass import (
    ai,
    api,
    categories,
    chat,
    docx,
    importer,
    notes,
    settings,
    summaries,
    transfer,
)

export_router = APIRouter(prefix="/api/export")
import_router = APIRouter(prefix="/api/import")


def _export_note(
    n: notes.Note, names: dict[int, str | None], kept: dict[int, summaries.Summary]
) -> dict[str, object]:
    item: dict[str, object] = {
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "tags": n.tags,
        "category": names.get(n.category_id),
        "created_at": n.created_at,
    }
    if (
        n.id in kept
    ):  # only notes that have one, so a file without summaries is as it always was
        item["summary"] = kept[n.id].model_dump()
    return item


@export_router.get("")
def export_notes() -> Response:
    """All notes as one downloadable JSON file; search and tag filters do not apply."""
    now = datetime.now(UTC)
    items = notes.export_all()
    kept = summaries.all_by_note()
    all_categories = categories.list_categories()
    names = {c.id: (None if c.default else c.name) for c in all_categories}
    document = {
        "format": transfer.EXPORT_FORMAT,
        "exported_at": now.isoformat(timespec="seconds"),
        "count": len(items),
        "categories": [c.name for c in all_categories if not c.default],
        "notes": [_export_note(n, names, kept) for n in items],
    }
    if (
        saved := chat.export_all()
    ):  # only when there are some, so older files stay as they were
        document["conversations"] = saved
    return Response(
        content=json.dumps(document, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="compass-export-{now:%Y-%m-%d}.json"',
            "Cache-Control": "no-store",
        },
    )


async def _upload(request: Request, limit: int) -> bytes:
    """The raw request body, refused with 413 above `limit` bytes."""
    too_large = HTTPException(
        status_code=413,
        detail={"code": "file_too_large", "limit_mb": limit // (1024 * 1024)},
    )
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise too_large
    # Stream and stop at the limit: a chunked body has no Content-Length to trust.
    raw = bytearray()
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > limit:
            raise too_large
    return bytes(raw)


@import_router.post("/file")
async def import_file(
    request: Request, name: str = "", parts: str = ""
) -> StreamingResponse:
    """A file (the raw body; `name` is its file name, which tells the type: .docx, .txt, .md, .pdf, or an image: .png, .jpg, .webp) turned into proposed notes, streamed as one JSON line per event
    (see `importer.run`): each part arrives as soon as the model has written it, with what the model
    found missing (`omitted`) and the numbers and links found in no note (`unmatched`). `parts` is a
    comma-separated list of part indexes to run again. Nothing is saved and the file is not kept; the
    user saves the confirmed proposals with `POST /api/notes/bulk`."""
    kind = PurePath(name).suffix.lower()
    limit = (
        api.MAX_IMAGE_BYTES
        if kind in importer.IMAGE_TYPES
        else api.MAX_PDF_BYTES
        if kind == ".pdf"
        else api.MAX_WORD_BYTES
    )
    raw = await _upload(request, limit)
    current = settings.current()
    try:
        wanted = await run_in_threadpool(importer.prepare, raw, current, name)
    except ai.AIError as problem:
        raise api.ai_error(problem) from None
    except docx.BadFile as problem:
        status = 413 if problem.code == "too_large" else 422
        raise HTTPException(status_code=status, detail={"code": problem.code}) from None
    only = {int(p) for p in parts.split(",") if p.strip().isdigit()} or None
    return StreamingResponse(
        api.lines(importer.run(current, wanted, only)),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store"},
    )


@import_router.post("")
async def import_notes(request: Request) -> dict[str, int]:
    """Restore an export file (the JSON body) one to one: everything in the database is replaced
    by the file. It is validated first; nothing changes unless the whole file is valid.
    """
    raw = await _upload(request, api.MAX_IMPORT_BYTES)
    try:
        document = json.loads(raw)
        parsed = await run_in_threadpool(transfer.parse_export, document)
    except (ValueError, RecursionError):  # not JSON, or nested absurdly deep
        raise HTTPException(status_code=422, detail={"code": "not_json"}) from None
    except transfer.BadExport as problem:
        raise HTTPException(
            status_code=422, detail={"code": problem.code, **problem.info}
        ) from None
    imported = await run_in_threadpool(
        notes.replace_all, parsed.notes, parsed.categories, parsed.conversations
    )
    return {"imported": imported}
