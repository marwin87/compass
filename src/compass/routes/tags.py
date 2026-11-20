from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from compass import (
    notes,
    tags,
)

router = APIRouter(prefix="/api/tags")


@router.get("")
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


@router.put("/{name:path}")
def rename_tag(name: str, data: TagRename) -> dict[str, object]:
    """Rename a tag on every note; renaming onto an existing tag merges the two."""
    try:
        return tags.rename(name, data.name)
    except tags.TagError as problem:
        raise _tag_error(problem) from None


@router.delete("/{name:path}")
def delete_tag(name: str) -> dict[str, object]:
    """Remove a tag from every note (the notes stay)."""
    try:
        return tags.delete(name)
    except tags.TagError as problem:
        raise _tag_error(problem) from None
