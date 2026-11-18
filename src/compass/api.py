import itertools
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, StringConstraints, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from compass import about as about_info
from compass import (
    ai,
    categories,
    chat,
    chunks,
    docx,
    importer,
    notes,
    settings,
    summaries,
    tags,
    transfer,
)

router = APIRouter(prefix="/api/notes")
tags_router = APIRouter(prefix="/api/tags")
export_router = APIRouter(prefix="/api/export")
import_router = APIRouter(prefix="/api/import")
categories_router = APIRouter(prefix="/api/categories")
settings_router = APIRouter(prefix="/api/settings")
ai_router = APIRouter(prefix="/api/ai")
chat_router = APIRouter(prefix="/api/chats")
about_router = APIRouter(prefix="/api/about")
data_router = APIRouter(prefix="/api/data")

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
MAX_WORD_BYTES = 5 * 1024 * 1024
MAX_BULK = 500  # notes per bulk save


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


class BulkNote(NoteIn):
    # By name, not id: an import may suggest a category that does not exist yet (it is created).
    category: str | None = Field(default=None, max_length=categories.MAX_NAME)


class BulkIn(BaseModel):
    notes: list[BulkNote] = Field(min_length=1, max_length=MAX_BULK)


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


AI_STATUS = {"not_enabled": 409, "not_configured": 409, "timeout": 504, "failed": 502}


@router.post("/{note_id}/translate")
def translate(
    note_id: int, to: Literal["en", "pl"]
) -> dict[str, str]:  # {"lang": to, "text": ...}
    """A preview of the note body translated into `to`; nothing is saved. A plain `def`: runs in the threadpool."""
    note = notes.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    try:
        return {"lang": to, "text": ai.translate(note.body, settings.current(), to)}
    except ai.AIError as problem:
        raise HTTPException(
            status_code=AI_STATUS[problem.code], detail={"code": problem.code}
        ) from None


@router.post("/{note_id}/summarize")
def summarize(note_id: int) -> summaries.Summary:
    """Write the summary and key points of the note and keep it (it replaces an earlier one); the note
    itself is not changed. A note with no text gets no model call and no summary (`text` is empty).
    A plain `def`: runs in the threadpool."""
    note = notes.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    try:
        text = ai.summarize(note.title, note.body, settings.current())
    except ai.AIError as problem:
        raise HTTPException(
            status_code=AI_STATUS[problem.code], detail={"code": problem.code}
        ) from None
    if not text:
        return summaries.Summary(text="", created_at=summaries.now(), stale=False)
    # The digest is of the note as it was sent: an edit made while the model worked makes this stale.
    saved = summaries.save(note.id, text, summaries.digest(note.title, note.body))
    if saved is None:
        raise HTTPException(status_code=404, detail="Note not found")
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


class TagRename(BaseModel):
    name: str


TAG_STATUS = {"name_invalid": 422, "not_found": 404}


def _tag_error(problem: tags.TagError) -> HTTPException:
    return HTTPException(
        status_code=TAG_STATUS.get(problem.code, 400),
        detail={"code": problem.code, **problem.info},
    )


@tags_router.put("/{name:path}")
def rename_tag(name: str, data: TagRename) -> dict[str, object]:
    """Rename a tag on every note; renaming onto an existing tag merges the two."""
    try:
        return tags.rename(name, data.name)
    except tags.TagError as problem:
        raise _tag_error(problem) from None


@tags_router.delete("/{name:path}")
def delete_tag(name: str) -> dict[str, object]:
    """Remove a tag from every note (the notes stay)."""
    try:
        return tags.delete(name)
    except tags.TagError as problem:
        raise _tag_error(problem) from None


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
    raw = await request.body()
    if len(raw) > limit:
        raise too_large
    return raw


def _lines(events: Iterator[dict[str, object]]) -> Iterator[str]:
    for event in events:
        yield json.dumps(event, ensure_ascii=False) + "\n"


@import_router.post("/file")
async def import_file(
    request: Request, name: str = "", parts: str = ""
) -> StreamingResponse:
    """A file (the raw body; `name` is its file name, which tells the type: .docx, .txt, .md) turned into proposed notes, streamed as one JSON line per event
    (see `importer.run`): each part arrives as soon as the model has written it, with what the model
    found missing (`omitted`) and the numbers and links found in no note (`unmatched`). `parts` is a
    comma-separated list of part indexes to run again. Nothing is saved and the file is not kept; the
    user saves the confirmed proposals with `POST /api/notes/bulk`."""
    raw = await _upload(request, MAX_WORD_BYTES)
    current = settings.current()
    try:
        wanted = await run_in_threadpool(importer.prepare, raw, current, name)
    except ai.AIError as problem:
        raise HTTPException(
            status_code=AI_STATUS[problem.code], detail={"code": problem.code}
        ) from None
    except docx.BadFile as problem:
        status = 413 if problem.code == "too_large" else 422
        raise HTTPException(status_code=status, detail={"code": problem.code}) from None
    only = {int(p) for p in parts.split(",") if p.strip().isdigit()} or None
    return StreamingResponse(
        _lines(importer.run(current, wanted, only)),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store"},
    )


@import_router.post("")
async def import_notes(request: Request) -> dict[str, int]:
    """Restore an export file (the JSON body) one to one: everything in the database is replaced
    by the file. It is validated first; nothing changes unless the whole file is valid.
    """
    raw = await _upload(request, MAX_IMPORT_BYTES)
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


@settings_router.get("")
def read_settings() -> dict[str, object]:
    return settings.current()


@settings_router.put("")
def write_settings(patch: dict[str, object]) -> dict[str, object]:
    """Partial update of known settings; one invalid key rejects the whole request."""
    try:
        return settings.update(patch)
    except settings.SettingError as problem:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_setting", "key": problem.key}
        ) from None


@ai_router.get("/status")
def ai_status() -> dict[str, object]:
    return ai.status(settings.current())


@ai_router.get("/index")
def index_status() -> dict[str, int]:
    """How many notes the chat's vector index covers (`indexed` of `total`)."""
    return chunks.status(settings.current())


@ai_router.post("/index")
def index_notes() -> StreamingResponse:
    """Embed the notes that are new or changed since the last run, streamed as one JSON line per event
    (`start`, `progress`, `done`, or `error`). Costs model calls, so it only runs when asked."""
    events = chunks.sync(settings.current())
    try:
        first = next(
            events
        )  # AI off / not configured / no embedding model: a plain error
    except ai.AIError as problem:
        raise HTTPException(
            status_code=AI_STATUS[problem.code], detail={"code": problem.code}
        ) from None
    return StreamingResponse(
        _lines(itertools.chain([first], events)),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store"},
    )


class Question(BaseModel):
    question: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=chat.MAX_QUESTION
        ),
    ]


@chat_router.get("")
def list_chats() -> list[chat.Conversation]:
    return chat.list_all()


@chat_router.post("", status_code=201)
def create_chat() -> chat.Conversation:
    return chat.create()


@chat_router.get("/{chat_id}")
def read_chat(chat_id: int) -> chat.Thread:
    thread = chat.get(chat_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return thread


class ChatTitle(BaseModel):
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]


@chat_router.patch("/{chat_id}")
def rename_chat(chat_id: int, data: ChatTitle) -> chat.Conversation:
    """Rename a conversation (the first question names it until then)."""
    renamed = chat.rename(chat_id, data.title)
    if renamed is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return renamed


@chat_router.delete("/{chat_id}", status_code=204)
def delete_chat(chat_id: int) -> None:
    if not chat.delete(chat_id):
        raise HTTPException(status_code=404, detail="Conversation not found")


@chat_router.post("/{chat_id}/ask")
def ask_chat(chat_id: int, data: Question) -> StreamingResponse:
    """One question of the conversation, answered from the notes and streamed as one JSON line per
    event (see `chat.answer`): `indexing`, `excerpts`, `delta`, then `done` with the cited notes, or
    `error`. Sends changed notes to the embedding model and excerpts of up to 8 notes to the chat model.
    A plain `def`: the first events (retrieval) run in the threadpool before the response starts."""
    current = settings.current()
    if chat.get(chat_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        ai.ready(current)
    except ai.AIError as problem:
        raise HTTPException(
            status_code=AI_STATUS[problem.code], detail={"code": problem.code}
        ) from None
    return StreamingResponse(
        _lines(chat.answer(current, chat_id, data.question)),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store"},
    )


@ai_router.delete("/index", status_code=204)
def clear_index() -> None:
    """Empty the chat's vector index (notes, search and conversations are untouched)."""
    chunks.clear()


@about_router.get("")
def read_about() -> dict[str, object]:
    return about_info.about()


@data_router.delete("", status_code=204)
def clear_data() -> None:
    """Remove every note, tag and category (the default one stays); settings are kept."""
    notes.replace_all([], [])
