from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, Field, StringConstraints
from starlette.responses import StreamingResponse

from compass import ai, api, settings
from compass.ai import chat

router = APIRouter(prefix="/api/chats")


class Question(BaseModel):
    question: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=chat.MAX_QUESTION
        ),
    ]


@router.get("")
def list_chats() -> list[chat.ChatListing]:
    return chat.list_all()


@router.post("", status_code=201)
def create_chat() -> chat.Conversation:
    return chat.create()


@router.get("/{chat_id}")
def read_chat(chat_id: int) -> chat.Thread:
    thread = chat.get(chat_id)
    if thread is None:
        raise api.not_found("Conversation")
    return thread


class ChatTitle(BaseModel):
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]


@router.patch("/{chat_id}")
def rename_chat(chat_id: int, data: ChatTitle) -> chat.Conversation:
    """Rename a conversation (the first question names it until then)."""
    renamed = chat.rename(chat_id, data.title)
    if renamed is None:
        raise api.not_found("Conversation")
    return renamed


@router.delete("/{chat_id}", status_code=204)
def delete_chat(chat_id: int) -> None:
    if not chat.delete(chat_id):
        raise api.not_found("Conversation")


class ChatIds(BaseModel):
    ids: Annotated[list[int], Field(min_length=1, max_length=5000)]


@router.post("/delete")
def delete_chats(data: ChatIds) -> dict[str, int]:
    """Delete the chosen conversations in one go (an id that no longer exists is skipped)."""
    return {"deleted": chat.delete_many(data.ids)}


@router.post("/{chat_id}/ask")
def ask_chat(chat_id: int, data: Question) -> StreamingResponse:
    """One question of the conversation, answered from the notes and streamed as one JSON line per
    event (see `chat.answer`): `indexing`, `excerpts`, `delta`, then `done` with the cited notes, or
    `error`. Sends changed notes to the embedding model and excerpts of up to 8 notes to the chat model.
    A plain `def`: the first events (retrieval) run in the threadpool before the response starts."""
    current = settings.current()
    if chat.get(chat_id) is None:
        raise api.not_found("Conversation")
    try:
        ai.ready(current)
    except ai.AIError as problem:
        raise api.ai_error(problem) from None
    return StreamingResponse(
        api.lines(chat.answer(current, chat_id, data.question)),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store"},
    )
