from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from compass import notes

router = APIRouter(prefix="/api/notes")


class NoteIn(BaseModel):
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    body: str = Field(default="", max_length=20000)


@router.post("", status_code=201)
def create(data: NoteIn) -> notes.Note:
    return notes.create_note(data.title, data.body)


@router.get("")
def search(q: str = "") -> list[notes.Note]:
    return notes.list_notes(q)


@router.get("/{note_id}")
def read(note_id: int) -> notes.Note:
    note = notes.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.put("/{note_id}")
def update(note_id: int, data: NoteIn) -> notes.Note:
    note = notes.update_note(note_id, data.title, data.body)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note
