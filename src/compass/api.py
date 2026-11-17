import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, StringConstraints, field_validator
from starlette.concurrency import run_in_threadpool

from compass import notes, transfer

router = APIRouter(prefix="/api/notes")
tags_router = APIRouter(prefix="/api/tags")
export_router = APIRouter(prefix="/api/export")
import_router = APIRouter(prefix="/api/import")

MAX_IMPORT_BYTES = (
    50 * 1024 * 1024
)  # an export is a few MB; this only stops runaway uploads


class NoteIn(BaseModel):
    title: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=notes.MAX_TITLE
        ),
    ]
    body: str = Field(default="", max_length=notes.MAX_BODY)
    # Full replacement: leaving it out clears the note's tags.
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def _normalize(cls, value: list[str]) -> list[str]:
        return notes.normalize_tags(value)


@router.post("", status_code=201)
def create(data: NoteIn) -> notes.Note:
    return notes.create_note(data.title, data.body, data.tags)


@router.get("")
def search(
    q: str = "", tag: Annotated[list[str] | None, Query()] = None
) -> list[notes.Note]:
    return notes.list_notes(q, tag or [])


@router.get("/{note_id}")
def read(note_id: int) -> notes.Note:
    note = notes.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.put("/{note_id}")
def update(note_id: int, data: NoteIn) -> notes.Note:
    note = notes.update_note(note_id, data.title, data.body, data.tags)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/{note_id}", status_code=204)
def delete(note_id: int) -> None:
    if not notes.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")


@tags_router.get("")
def list_tags() -> list[notes.TagCount]:
    return notes.list_tags()


@export_router.get("")
def export_notes() -> Response:
    """All notes as one downloadable JSON file; search and tag filters do not apply."""
    now = datetime.now(UTC)
    items = notes.export_all()
    document = {
        "format": transfer.EXPORT_FORMAT,
        "version": transfer.EXPORT_VERSION,
        "exported_at": now.isoformat(timespec="seconds"),
        "count": len(items),
        "notes": [
            {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "tags": n.tags,
                "created_at": n.created_at,
            }
            for n in items
        ],
    }
    return Response(
        content=json.dumps(document, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="compass-export-{now:%Y-%m-%d}.json"',
            "Cache-Control": "no-store",
        },
    )


@import_router.post("")
async def import_notes(request: Request) -> dict[str, int]:
    """Load an export file (the JSON body). Everything is validated first; nothing is written
    unless the whole file is valid. Notes already present are skipped."""
    too_large = HTTPException(
        status_code=413,
        detail={
            "code": "file_too_large",
            "limit_mb": MAX_IMPORT_BYTES // (1024 * 1024),
        },
    )
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_IMPORT_BYTES:
        raise too_large
    raw = await request.body()
    if len(raw) > MAX_IMPORT_BYTES:
        raise too_large
    try:
        document = json.loads(raw)
        parsed = await run_in_threadpool(transfer.parse_export, document)
    except (ValueError, RecursionError):  # not JSON, or nested absurdly deep
        raise HTTPException(status_code=422, detail={"code": "not_json"}) from None
    except transfer.BadExport as problem:
        raise HTTPException(
            status_code=422, detail={"code": problem.code, **problem.info}
        ) from None
    imported, skipped = await run_in_threadpool(notes.import_notes, parsed)
    return {"imported": imported, "skipped": skipped, "total": imported + skipped}
