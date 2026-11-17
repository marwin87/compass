import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field, StringConstraints, field_validator

from compass import notes

router = APIRouter(prefix="/api/notes")
tags_router = APIRouter(prefix="/api/tags")
export_router = APIRouter(prefix="/api/export")

EXPORT_FORMAT = "compass-export"
EXPORT_VERSION = 1


class NoteIn(BaseModel):
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    body: str = Field(default="", max_length=20000)
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
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
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
