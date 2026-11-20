from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, StringConstraints, field_validator

from compass import ai, api, db, notes, settings
from compass.notes import categories, summaries

router = APIRouter(prefix="/api/notes")


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
        raise api.category_error(problem) from None


class BulkNote(NoteIn):
    # By name, not id: an import may suggest a category that does not exist yet (it is created).
    category: str | None = Field(default=None, max_length=categories.MAX_NAME)


class BulkIn(BaseModel):
    notes: list[BulkNote] = Field(min_length=1, max_length=api.MAX_BULK)


@router.post("/bulk", status_code=201)
def create_bulk(data: BulkIn) -> dict[str, int]:
    """Save several notes at once (the confirmed proposals of a file import); all or none."""
    try:
        return {
            "created": notes.create_many(
                [(n.title, n.body, n.tags, n.category) for n in data.notes]
            )
        }
    except categories.CategoryError as problem:
        raise api.category_error(problem) from None


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
        raise api.not_found("Note")
    return note


@router.post("/{note_id}/translate")
def translate(
    note_id: int, to: Literal["en", "pl"]
) -> dict[str, str]:  # {"lang": to, "text": ...}
    """A preview of the note body translated into `to`; nothing is saved. A plain `def`: runs in the threadpool."""
    note = notes.get_note(note_id)
    if note is None:
        raise api.not_found("Note")
    try:
        return {"lang": to, "text": ai.translate(note.body, settings.current(), to)}
    except ai.AIError as problem:
        raise api.ai_error(problem) from None


@router.post("/{note_id}/summarize")
def summarize(note_id: int) -> summaries.Summary:
    """Write the summary and key points of the note and keep it (it replaces an earlier one); the note
    itself is not changed. A note with no text gets no model call and no summary (`text` is empty).
    A plain `def`: runs in the threadpool."""
    note = notes.get_note(note_id)
    if note is None:
        raise api.not_found("Note")
    try:
        text = ai.summarize(note.title, note.body, settings.current())
    except ai.AIError as problem:
        raise api.ai_error(problem) from None
    if not text:
        return summaries.Summary(text="", created_at=db.now(), stale=False)
    # The digest is of the note as it was sent: an edit made while the model worked makes this stale.
    saved = summaries.save(note.id, text, summaries.digest(note.title, note.body))
    if saved is None:
        raise api.not_found("Note")
    return saved


@router.get("/{note_id}/summary")
def read_summary(note_id: int) -> summaries.Summary | None:
    """The kept summary of a note, or null (with `stale` set when the note changed after it)."""
    return summaries.get(note_id)


@router.delete("/{note_id}/summary", status_code=204)
def delete_summary(note_id: int) -> None:
    summaries.delete(note_id)


@router.put("/{note_id}")
def update(note_id: int, data: NoteIn) -> notes.Note:
    try:
        note = notes.update_note(
            note_id, data.title, data.body, data.tags, data.category_id
        )
    except categories.CategoryError as problem:
        raise api.category_error(problem) from None
    if note is None:
        raise api.not_found("Note")
    return note


@router.delete("/{note_id}", status_code=204)
def delete(note_id: int) -> None:
    if not notes.delete_note(note_id):
        raise api.not_found("Note")
