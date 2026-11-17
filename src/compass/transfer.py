"""Reading an export file (the one `GET /api/export` produces); no database access here.

The whole document is validated before anything is written, so a bad file changes nothing.
Problems are reported as a `BadExport` carrying a machine-readable `code`; the page turns
those codes into translated messages.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from compass import categories
from compass.notes import MAX_BODY, MAX_TITLE, ParsedNote, normalize_tags

EXPORT_FORMAT = "compass-export"


class BadExport(Exception):
    def __init__(self, code: str, **info: object) -> None:
        super().__init__(code)
        self.code = code
        self.info = info


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _bad(index: int, field: str) -> BadExport:
    return BadExport("invalid_note", index=index, field=field)


def _parse_note(index: int, raw: object) -> ParsedNote:
    if not isinstance(raw, dict):
        raise _bad(index, "note")
    title = raw.get("title")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= MAX_TITLE:
        raise _bad(index, "title")
    body = raw.get("body")
    if not isinstance(body, str) or len(body) > MAX_BODY:
        raise _bad(index, "body")
    tags = raw.get("tags")
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise _bad(index, "tags")
    try:
        clean_tags = normalize_tags(tags)
    except ValueError:
        raise _bad(index, "tags") from None
    created_at = raw.get("created_at")
    if not isinstance(created_at, str):
        raise _bad(index, "created_at")
    try:
        when = datetime.fromisoformat(created_at)
    except ValueError:
        raise _bad(index, "created_at") from None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    category = raw.get("category")  # optional: absent or null means the default
    if category is not None:
        if not isinstance(category, str):
            raise _bad(index, "category")
        try:
            category = " ".join(category.split()) or None
            if category is not None:
                categories.normalize(category)
        except categories.CategoryError as problem:
            if problem.code != "name_reserved":  # the default's own labels are fine
                raise _bad(index, "category") from None
    return ParsedNote(
        title.strip(), body, tuple(clean_tags), created_at, when, category
    )


@dataclass(frozen=True)
class ParsedExport:
    notes: list[ParsedNote]  # file order (newest first)
    categories: list[str]  # every category the file lists, with or without notes


def parse_export(document: object) -> ParsedExport:
    """Validate a whole export document."""
    if not isinstance(document, dict) or document.get("format") != EXPORT_FORMAT:
        raise BadExport("not_an_export")
    items = document.get("notes")
    if not isinstance(items, list):
        raise BadExport("invalid_file")
    count = document.get("count")
    if not _is_int(count) or count != len(items):
        raise BadExport(
            "count_mismatch",
            expected=count if _is_int(count) else None,
            actual=len(items),
        )
    names = document.get("categories", [])  # optional: older files list none
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise BadExport("invalid_file")
    for name in names:
        try:
            categories.normalize(name)
        except categories.CategoryError as problem:
            if problem.code != "name_reserved":
                raise BadExport("invalid_file") from None
    return ParsedExport([_parse_note(i, raw) for i, raw in enumerate(items, 1)], names)
