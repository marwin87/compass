from fastapi import APIRouter
from pydantic import BaseModel

from compass import (
    api,
    categories,
)

router = APIRouter(prefix="/api/categories")


class CategoryIn(BaseModel):
    name: str


@router.get("")
def list_categories() -> list[categories.Category]:
    return categories.list_categories()


@router.post("", status_code=201)
def create_category(data: CategoryIn) -> categories.Category:
    try:
        return categories.create(data.name)
    except categories.CategoryError as problem:
        raise api.category_error(problem) from None


@router.put("/{category_id}")
def rename_category(category_id: int, data: CategoryIn) -> categories.Category:
    try:
        return categories.rename(category_id, data.name)
    except categories.CategoryError as problem:
        raise api.category_error(problem) from None


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int) -> None:
    try:
        categories.delete(category_id)
    except categories.CategoryError as problem:
        raise api.category_error(problem) from None
