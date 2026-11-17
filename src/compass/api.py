import json
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, StringConstraints, field_validator
from starlette.concurrency import run_in_threadpool

from compass import categories, notes, transfer

router = APIRouter(prefix="/api/notes")
tags_router = APIRouter(prefix="/api/tags")
export_router = APIRouter(prefix="/api/export")
import_router = APIRouter(prefix="/api/import")
categories_router = APIRouter(prefix="/api/categories")

CATEGORY_STATUS = {
    "name_invalid": 422,
    "name_reserved": 422,
    "invalid_category": 422,
    "name_taken": 409,
    "default_category": 409,
    "not_empty": 409,
    "not_found": 404,
}


def _category_error(problem: categories.CategoryError) -> HTTPException:
    return HTTPException(
        status_code=CATEGORY_STATUS.get(problem.code, 400),
        detail={"code": problem.code, **problem.info},
    )


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
    # Full replacement too: leaving it out puts the note in the default category.
    category_id: int | None = None

    @field_validator("tags")
    @classmethod
    def _normalize(cls, value: list[str]) -> list[str]:
        return notes.normalize_tags(value)


@router.post("", status_code=201)
def create(data: NoteIn) -> notes.Note:
    try:
        return notes.create_note(data.title, data.body, data.tags, data.category_id)
    except categories.CategoryError as problem:
        raise _category_error(problem) from None


@router.get("")
def search(
    q: str = "",
    tag: Annotated[list[str] | None, Query()] = None,
    category_id: int | None = None,
    sort: Literal["title_asc", "title_desc", "date_asc", "date_desc"] | None = None,
) -> list[notes.Note]:
    return notes.list_notes(q, tag or [], category_id, sort)


@router.get("/{note_id}")
def read(note_id: int) -> notes.Note:
    note = notes.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.put("/{note_id}")
def update(note_id: int, data: NoteIn) -> notes.Note:
    try:
        note = notes.update_note(
            note_id, data.title, data.body, data.tags, data.category_id
        )
    except categories.CategoryError as problem:
        raise _category_error(problem) from None
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
    all_categories = categories.list_categories()
    names = {c.id: (None if c.default else c.name) for c in all_categories}
    document = {
        "format": transfer.EXPORT_FORMAT,
        "exported_at": now.isoformat(timespec="seconds"),
        "count": len(items),
        "categories": [c.name for c in all_categories if not c.default],
        "notes": [
            {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "tags": n.tags,
                "category": names.get(n.category_id),
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
    """Restore an export file (the JSON body) one to one: everything in the database is replaced
    by the file. It is validated first; nothing changes unless the whole file is valid."""
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
    imported = await run_in_threadpool(
        notes.replace_all, parsed.notes, parsed.categories
    )
    return {"imported": imported}


class CategoryIn(BaseModel):
    name: str


@categories_router.get("")
def list_categories() -> list[categories.Category]:
    return categories.list_categories()


@categories_router.post("", status_code=201)
def create_category(data: CategoryIn) -> categories.Category:
    try:
        return categories.create(data.name)
    except categories.CategoryError as problem:
        raise _category_error(problem) from None


@categories_router.put("/{category_id}")
def rename_category(category_id: int, data: CategoryIn) -> categories.Category:
    try:
        return categories.rename(category_id, data.name)
    except categories.CategoryError as problem:
        raise _category_error(problem) from None


@categories_router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int) -> None:
    try:
        categories.delete(category_id)
    except categories.CategoryError as problem:
        raise _category_error(problem) from None
