"""Reading an export file (the one `GET /api/export` produces); no database access here.

The whole document is validated before anything is written, so a bad file changes nothing.
Problems are reported as a `BadExport` carrying a machine-readable `code`; the page turns
those codes into translated messages.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from compass import categories
from compass.notes import (
    MAX_BODY,
    MAX_TITLE,
    ParsedConversation,
    ParsedMessage,
    ParsedNote,
    ParsedSource,
    ParsedSummary,
    normalize_tags,
)
from compass.summaries import MAX_SUMMARY

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


def _parse_summary(index: int, raw: object) -> ParsedSummary | None:
    """The optional `summary` of a note: {text, created_at, stale}."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise _bad(index, "summary")
    text, created_at, stale = raw.get("text"), raw.get("created_at"), raw.get("stale")
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= MAX_SUMMARY:
        raise _bad(index, "summary")
    if not isinstance(created_at, str) or not isinstance(stale, bool):
        raise _bad(index, "summary")
    try:
        datetime.fromisoformat(created_at)
    except ValueError:
        raise _bad(index, "summary") from None
    return ParsedSummary(text, created_at, stale)


def _parse_tags(index: int, raw: object) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(t, str) for t in raw):
        raise _bad(index, "tags")
    try:
        return normalize_tags(raw)
    except ValueError:
        raise _bad(index, "tags") from None


def _parse_when(index: int, raw: object) -> datetime:
    if not isinstance(raw, str):
        raise _bad(index, "created_at")
    try:
        when = datetime.fromisoformat(raw)
    except ValueError:
        raise _bad(index, "created_at") from None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _parse_category(index: int, raw: object) -> str | None:
    """Optional: absent or null means the default."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise _bad(index, "category")
    name = " ".join(raw.split()) or None
    if name is not None:
        try:
            categories.normalize(name)
        except categories.CategoryError as problem:
            if problem.code != "name_reserved":  # the default's own labels are fine
                raise _bad(index, "category") from None
    return name


def _parse_note(index: int, raw: object) -> ParsedNote:
    if not isinstance(raw, dict):
        raise _bad(index, "note")
    title = raw.get("title")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= MAX_TITLE:
        raise _bad(index, "title")
    body = raw.get("body")
    if not isinstance(body, str) or len(body) > MAX_BODY:
        raise _bad(index, "body")
    return ParsedNote(
        title.strip(),
        body,
        tuple(_parse_tags(index, raw.get("tags"))),
        raw["created_at"] if isinstance(raw.get("created_at"), str) else "",
        _parse_when(index, raw.get("created_at")),
        _parse_category(index, raw.get("category")),
        _parse_summary(index, raw.get("summary")),
        raw["id"] if _is_int(raw.get("id")) else None,
    )


MAX_CONVERSATIONS = 1000
MAX_MESSAGES = 1000
MAX_TEXT = 100_000  # one question or answer


def _bad_chat(index: int, field: str) -> BadExport:
    return BadExport("invalid_conversation", index=index, field=field)


def _iso(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _parse_message(index: int, raw: object) -> ParsedMessage:
    if not isinstance(raw, dict):
        raise _bad_chat(index, "message")
    role, text, created_at = raw.get("role"), raw.get("text"), raw.get("created_at")
    if role not in ("user", "assistant"):
        raise _bad_chat(index, "role")
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= MAX_TEXT:
        raise _bad_chat(index, "text")
    if not _iso(created_at):
        raise _bad_chat(index, "created_at")
    cited = raw.get("sources", [])
    if not isinstance(cited, list) or (role == "user" and cited):
        raise _bad_chat(index, "sources")
    sources = []
    for s in cited:
        if not isinstance(s, dict):
            raise _bad_chat(index, "sources")
        note, title = s.get("note"), s.get("title")
        if (note is not None and not _is_int(note)) or not isinstance(title, str):
            raise _bad_chat(index, "sources")
        if len(title) > MAX_TITLE:
            raise _bad_chat(index, "sources")
        sources.append(ParsedSource(note, title))
    assert isinstance(created_at, str)
    return ParsedMessage(role, text, created_at, tuple(sources))


def _parse_conversations(raw: object) -> list[ParsedConversation]:
    """The optional `conversations` of an export: saved chats with the notes their answers cite."""
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_CONVERSATIONS:
        raise BadExport("invalid_file")
    out = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise _bad_chat(index, "conversation")
        title, created_at, messages = (
            item.get("title"),
            item.get("created_at"),
            item.get("messages"),
        )
        if not isinstance(title, str) or len(title) > MAX_TITLE:
            raise _bad_chat(index, "title")
        if not _iso(created_at):
            raise _bad_chat(index, "created_at")
        if not isinstance(messages, list) or len(messages) > MAX_MESSAGES:
            raise _bad_chat(index, "messages")
        assert isinstance(created_at, str)
        out.append(
            ParsedConversation(
                title,
                created_at,
                tuple(_parse_message(index, m) for m in messages),
            )
        )
    return out


@dataclass(frozen=True)
class ParsedExport:
    notes: list[ParsedNote]  # file order (newest first)
    categories: list[str]  # every category the file lists, with or without notes
    conversations: list[ParsedConversation]


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
    return ParsedExport(
        [_parse_note(i, raw) for i, raw in enumerate(items, 1)],
        names,
        _parse_conversations(document.get("conversations")),
    )
