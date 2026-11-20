"""What the HTTP routes (`compass.routes`) share: upload limits, error-code to status maps, NDJSON streaming.

The limits live here, as plain module attributes the routes read when a request arrives, so one place
sets them (and a test can lower one).
"""

import json
from collections.abc import Iterator

from fastapi import HTTPException

from compass import ai, categories

CATEGORY_STATUS = {
    "name_invalid": 422,
    "name_reserved": 422,
    "invalid_category": 422,
    "name_taken": 409,
    "default_category": 409,
    "not_empty": 409,
    "not_found": 404,
}
AI_STATUS = {"not_enabled": 409, "not_configured": 409, "timeout": 504, "failed": 502}

MAX_IMPORT_BYTES = (
    50 * 1024 * 1024
)  # an export is a few MB; this only stops runaway uploads
MAX_WORD_BYTES = 5 * 1024 * 1024
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # a phone photo is a few MB; no resizing here
MAX_BULK = 500  # notes per bulk save


def category_error(problem: categories.CategoryError) -> HTTPException:
    return HTTPException(
        status_code=CATEGORY_STATUS.get(problem.code, 400),
        detail={"code": problem.code, **problem.info},
    )


def ai_error(problem: ai.AIError) -> HTTPException:
    return HTTPException(
        status_code=AI_STATUS[problem.code], detail={"code": problem.code}
    )


def lines(events: Iterator[dict[str, object]]) -> Iterator[str]:
    for event in events:
        yield json.dumps(event, ensure_ascii=False) + "\n"
