from datetime import UTC, datetime

from fastapi import APIRouter

from compass import api, notes, settings

router = APIRouter(prefix="/api/trash")


class TrashItem(notes.TrashedNote):
    days_left: (
        int | None
    )  # until it is deleted for good (None: the Trash is never emptied by itself)


def _days() -> int:
    days = settings.current()["trash_days"]
    assert isinstance(days, int)
    return days


def _item(note: notes.TrashedNote, days: int) -> TrashItem:
    left = None
    if days > 0:
        age = (datetime.now(UTC) - datetime.fromisoformat(note.deleted_at)).days
        left = max(0, days - age)
    return TrashItem(**note.model_dump(), days_left=left)


@router.get("")
def read_trash(q: str = "") -> list[TrashItem]:
    """The notes in the Trash, most recently deleted first; those past `trash_days` are deleted first."""
    days = _days()
    notes.purge_expired(days)
    return [_item(n, days) for n in notes.list_trash(q)]


@router.get("/count")
def count_trash() -> dict[str, int]:
    notes.purge_expired(_days())
    return {"count": notes.trash_count()}


@router.post("/{note_id}/restore")
def restore(note_id: int) -> notes.Note:
    """Take a note out of the Trash (its tags come back, it is searchable at once)."""
    note = notes.restore_note(note_id)
    if note is None:
        raise api.not_found("Note")
    return note


@router.delete("/{note_id}", status_code=204)
def purge(note_id: int) -> None:
    """Delete a note in the Trash for good."""
    if not notes.purge_note(note_id):
        raise api.not_found("Note")


@router.delete("")
def empty() -> dict[str, int]:
    """Delete everything in the Trash for good."""
    return {"deleted": notes.empty_trash()}
