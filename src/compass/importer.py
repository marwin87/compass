"""Turn a Word file into proposed notes (nothing is saved here).

The model reads the file part by part, understands it and writes self-contained Markdown notes
(one per topic). A second call per part then compares the source with those notes and lists what
is missing; the code also lists numbers and links of the part that appear in no note.

`run` yields one event per part as soon as it is ready, so the user can review and save while the
rest is still being written. A part that fails is reported with its reason and does not stop the
others; it can be run again alone (`only`).
"""

import json
import re
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from compass import ai, docx, notes

MAX_TEXT = (
    100_000  # characters of extracted text; the cost guard until a cost estimate exists
)
WINDOW = 8_000  # characters of the file the model reads in one call
WORKERS = (
    4  # ponytail: fixed pool; parts are independent, so a few calls run side by side
)
CALL_TIMEOUT = 120  # writing notes is a long answer, longer than a translation
TOKEN = re.compile(r"https?://\S+|\d{2,}")

WRITE = (
    "You turn a part of a document into notes for a personal knowledge base. Read the text, understand "
    "it, and write separate notes, one per topic; each note must make sense on its own and be easy to "
    "find by search (a clear, specific title). Write each note as tidy Markdown: short paragraphs, "
    "'##' headings for sub-topics, bullet or numbered lists for enumerations and steps, a table for "
    "tabular data, fenced code for code. Keep ALL facts, numbers, names, steps, code and links: improve "
    "structure and wording, but never drop a detail, invent anything or add commentary. Write in the "
    "language of the document. The text may begin or end in the middle of a topic; still write notes "
    'for what is there. Reply with a JSON array only: [{"title": "...", "body": "..."}].'
)
CHECK = (
    "You receive a SOURCE text and the NOTES written from it. List the facts, steps, numbers, names, "
    "code or whole passages of the SOURCE that are missing from the NOTES or whose meaning was changed. "
    "Ignore differences of wording and layout. Reply with a JSON array of short strings in the "
    "language of the source, or [] when nothing is missing."
)


@dataclass(frozen=True)
class Proposal:
    title: str
    body: str


def _text(blocks: list[docx.Block]) -> str:
    return "\n\n".join(
        ("#" * b.heading + " " + b.text) if b.heading else b.text for b in blocks
    )


def windows(blocks: list[docx.Block]) -> list[list[docx.Block]]:
    """Parts of the file of about WINDOW characters, cut at a top-level heading when one is near."""
    top = min((b.heading for b in blocks if b.heading), default=0)
    out: list[list[docx.Block]] = [[]]
    size = 0
    for block in blocks:
        for i in range(0, max(len(block.text), 1), WINDOW):  # a huge paragraph is cut
            piece = docx.Block(block.heading, block.text[i : i + WINDOW])
            n = len(piece.text)
            heading_break = top and piece.heading == top and size >= WINDOW // 2
            if (size + n > WINDOW or heading_break) and out[-1]:
                out.append([])
                size = 0
            out[-1].append(piece)
            size += n + 2
    return out


def _ask_json(s: dict[str, object], system: str, user: str) -> list[object]:
    """A JSON array from the model; one retry when the reply is not usable."""
    for _ in range(2):
        reply = ai.ask(s, system, user, CALL_TIMEOUT)
        try:
            data = json.loads(reply[reply.index("[") : reply.rindex("]") + 1])
        except ValueError:
            continue
        if isinstance(data, list):
            return data
    raise ai.AIError("failed", "the model did not return a usable list")


def _fit(title: str, body: str) -> list[Proposal]:
    """One proposal, or several when the text is longer than a note may be (cut between paragraphs)."""
    title = title[: notes.MAX_TITLE - 10]
    if len(body) <= notes.MAX_BODY:
        return [Proposal(title, body)]
    paragraphs = [p for p in body.split("\n\n") if p.strip()]
    parts: list[str] = [""]
    for p in paragraphs:
        for i in range(0, len(p), notes.MAX_BODY):
            piece = p[i : i + notes.MAX_BODY]
            if len(parts[-1]) + len(piece) + 2 > notes.MAX_BODY:
                parts.append("")
            parts[-1] += ("\n\n" if parts[-1] else "") + piece
    return [
        Proposal(title if i == 0 else f"{title} ({i + 1})", part)
        for i, part in enumerate(parts)
    ]


def _proposals(items: list[object]) -> list[Proposal]:
    found: list[Proposal] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title, body = item.get("title"), item.get("body")
        if (
            isinstance(title, str)
            and isinstance(body, str)
            and title.strip()
            and body.strip()
        ):
            found += _fit(title.strip(), body.strip())
    return found


def _unmatched(source: str, found: list[Proposal]) -> list[str]:
    written = "\n".join(f"{p.title}\n{p.body}" for p in found)
    seen = dict.fromkeys(t.rstrip(".,;:)") for t in TOKEN.findall(source))
    return [t for t in seen if t not in written][:30]


def _label(blocks: list[docx.Block]) -> str:
    """A few words that tell the user which part of the file this is."""
    return " ".join(blocks[0].text.split())[:60]


def _event(
    s: dict[str, object], index: int, blocks: list[docx.Block], stop: threading.Event
) -> dict[str, object]:
    """The result of one part: `part` (notes, what is missing) or `error` (code and reason)."""
    if stop.is_set():  # the user left: do not pay for the rest
        return {"type": "error", "index": index, "code": "failed", "detail": ""}
    source = _text(blocks)
    try:
        found = _proposals(_ask_json(s, WRITE, source))
    except ai.AIError as problem:
        return {
            "type": "error",
            "index": index,
            "code": problem.code,
            "detail": problem.detail,
        }
    omitted: list[str] = []
    unchecked = False
    if found:
        written = "\n\n".join(f"## {p.title}\n\n{p.body}" for p in found)
        try:
            missing = _ask_json(s, CHECK, f"SOURCE:\n{source}\n\nNOTES:\n{written}")
            omitted = [m.strip() for m in missing if isinstance(m, str) and m.strip()]
        except ai.AIError:  # the notes are good; only the check did not work
            unchecked = True
    return {
        "type": "part",
        "index": index,
        "notes": [{"title": p.title, "body": p.body} for p in found],
        "omitted": omitted,
        "unmatched": _unmatched(source, found) if found else [],
        "unchecked": unchecked,
    }


def prepare(raw: bytes, s: dict[str, object]) -> list[list[docx.Block]]:
    """The parts of a .docx file, after every check that can fail before any model call.
    Raises ai.AIError (AI off or not configured) and docx.BadDocx."""
    ai.ready(s)
    blocks = docx.extract(raw)
    if sum(len(b.text) for b in blocks) > MAX_TEXT:
        raise docx.BadDocx("too_large")
    return windows(blocks)


def run(
    s: dict[str, object], parts: list[list[docx.Block]], only: set[int] | None = None
) -> Iterator[dict[str, object]]:
    """Events in file order: `start` (part count and labels), one `part` or `error` per part
    (all parts, or only the indexes in `only`), then `done`. Nothing is saved."""
    todo = [i for i in range(len(parts)) if only is None or i in only]
    yield {
        "type": "start",
        "total": len(parts),
        "labels": [_label(p) for p in parts],
        "parts": todo,
    }
    stop = threading.Event()
    with ThreadPoolExecutor(WORKERS) as pool:
        try:
            yield from pool.map(lambda i: _event(s, i, parts[i], stop), todo)
        finally:
            stop.set()  # the client went away: parts not started yet make no call
    yield {"type": "done"}
