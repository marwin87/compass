"""Turn a Word, PDF, text or image file into proposed notes (nothing is saved here).

An image is first read by the vision model into Markdown text (`ai.read_image`); from there it is a text
file like any other. The image itself is never stored.

The model reads the file part by part, understands it and writes self-contained Markdown notes
(one per topic). A second call per part then compares the source with those notes and lists what
is missing; the code also lists numbers and links of the part that appear in no note. The model also
suggests a category and tags for each note, from the existing ones first; the code maps what it
returns onto the existing names (case and accents ignored) so near-duplicates do not pile up.

`run` streams events while the model is still writing: every note is sent the moment the model has
finished it, and parts run side by side, so the user can review and save while the rest is still coming. A part that fails is reported with its reason and does not stop the
others; it can be run again alone (`only`).
"""

import json
import queue
import re
import threading
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import PurePath

from compass import ai, categories, docx, notes, pdf, textfile
from compass.search import fold

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
    'for what is there. Reply with a JSON array only: [{"title": "...", "body": "...", '
    '"category": "..." or null, "tags": ["..."]}].'
)
SUGGEST = (
    "Also give every note a category and tags. Existing categories: {categories}. Existing tags: "
    "{tags}. Take the category from the existing ones when one fits (copy it exactly); only when none "
    "fits give a short new name, or null. Give 2 to 5 short lowercase tags. Reuse an existing tag "
    "whenever it fits; make a new tag only when none fits, and never a near-duplicate of an existing "
    "one (another spelling, language, singular or plural)."
)
MAX_KNOWN = 150  # ponytail: the most used tags only; a long tail does not fit a prompt, a search of them could
MAX_SUGGESTED_TAGS = 5
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
    category: str | None = None  # an existing name, or a new one the model suggests
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Vocab:
    """What exists already, so suggestions can reuse it: folded name -> name."""

    categories: dict[str, str]
    tags: dict[str, str]
    titles: frozenset[str] = frozenset()  # folded titles of the notes that exist

    def prompt(self) -> str:
        def show(names: dict[str, str]) -> str:
            return (
                json.dumps(list(names.values()), ensure_ascii=False)
                if names
                else "(none yet)"
            )

        return (
            WRITE
            + " "
            + SUGGEST.format(categories=show(self.categories), tags=show(self.tags))
        )


def vocabulary() -> Vocab:
    cats = [c.name for c in categories.list_categories() if not c.default]
    tags = [t.name for t in notes.list_tags()]  # most used first
    return Vocab(
        {fold(n): n for n in cats[:MAX_KNOWN]},
        {fold(n): n for n in tags[:MAX_KNOWN]},
        frozenset(fold(t.strip()) for t in notes.titles()),
    )


def _category(raw: object, known: Vocab) -> str | None:
    clean = " ".join(raw.split()) if isinstance(raw, str) else ""
    if not clean or fold(clean) in categories.RESERVED_KEYS:
        return None
    return known.categories.get(fold(clean)) or clean[: categories.MAX_NAME]


def _tags(raw: object, known: Vocab) -> tuple[str, ...]:
    found: dict[str, None] = {}
    for item in raw if isinstance(raw, list) else []:
        clean = " ".join(item.lower().split()) if isinstance(item, str) else ""
        if clean and "," not in clean and len(clean) <= notes.MAX_TAG_LEN:
            found[known.tags.get(fold(clean), clean)] = None
    return tuple(found)[:MAX_SUGGESTED_TAGS]


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


def _fit(
    title: str, body: str, category: str | None = None, tags: tuple[str, ...] = ()
) -> list[Proposal]:
    """One proposal, or several when the text is longer than a note may be (cut between paragraphs)."""
    title = title[: notes.MAX_TITLE - 10]
    if len(body) <= notes.MAX_BODY:
        return [Proposal(title, body, category, tags)]
    paragraphs = [p for p in body.split("\n\n") if p.strip()]
    parts: list[str] = [""]
    for p in paragraphs:
        for i in range(0, len(p), notes.MAX_BODY):
            piece = p[i : i + notes.MAX_BODY]
            if len(parts[-1]) + len(piece) + 2 > notes.MAX_BODY:
                parts.append("")
            parts[-1] += ("\n\n" if parts[-1] else "") + piece
    return [
        Proposal(title if i == 0 else f"{title} ({i + 1})", part, category, tags)
        for i, part in enumerate(parts)
    ]


def _proposals(items: list[object], known: Vocab) -> list[Proposal]:
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
            found += _fit(
                title.strip(),
                body.strip(),
                _category(item.get("category"), known),
                _tags(item.get("tags"), known),
            )
    return found


def _unmatched(source: str, found: list[Proposal]) -> list[str]:
    written = "\n".join(f"{p.title}\n{p.body}" for p in found)
    seen = dict.fromkeys(t.rstrip(".,;:)") for t in TOKEN.findall(source))
    return [t for t in seen if t not in written][:30]


def _label(blocks: list[docx.Block]) -> str:
    """A few words that tell the user which part of the file this is."""
    return " ".join(blocks[0].text.split())[:60]


END = (
    object()
)  # yielded by `_objects` when the array was closed: an empty array is an answer too


def _objects(pieces: Iterable[str]) -> Iterator[object]:
    """The complete items of a JSON array, each as soon as its last character has arrived, then END."""
    decoder = json.JSONDecoder()
    text, pos = "", -1
    for piece in pieces:
        text += piece
        if pos < 0:
            start = text.find("[")  # skips any words or a code fence before the array
            if start < 0:
                continue
            pos = start + 1
        while True:
            while pos < len(text) and text[pos] in " \t\r\n,":
                pos += 1
            if pos < len(text) and text[pos] == "]":
                yield END
                return
            if pos >= len(text):
                break
            try:
                item, pos = decoder.raw_decode(text, pos)
            except ValueError:  # the item is not finished yet
                break
            yield item


def _items(
    s: dict[str, object], system: str, source: str, stop: threading.Event
) -> Iterator[object]:
    """The notes the model writes for one part, one by one. Tries once more only when the first try
    gave nothing (after a note was shown, starting over would show it twice)."""
    for _ in range(2):
        got = False
        for item in _objects(ai.stream(s, system, source, CALL_TIMEOUT)):
            got = True
            if item is END:
                return
            yield item
            if stop.is_set():
                return
        if got:
            return
    raise ai.AIError("failed", "the model did not return usable notes")


def _part_events(
    s: dict[str, object],
    index: int,
    blocks: list[docx.Block],
    stop: threading.Event,
    known: Vocab,
) -> Iterator[dict[str, object]]:
    """Events of one part: `note` for each note as it is written, then `written`, then `check`
    (what the model found missing). `error` (code and reason) ends a part that failed."""
    source = _text(blocks)
    found: list[Proposal] = []
    try:
        for item in _items(s, known.prompt(), source, stop):
            for p in _proposals([item], known):
                found.append(p)
                yield {
                    "type": "note",
                    "index": index,
                    "note": {
                        "title": p.title,
                        "body": p.body,
                        "category": p.category,
                        "tags": list(p.tags),
                        "exists": fold(p.title.strip())
                        in known.titles,  # a note with this title is already saved
                    },
                }
    except ai.AIError as problem:
        yield {
            "type": "error",
            "index": index,
            "code": problem.code,
            "detail": problem.detail,
        }
        return
    if stop.is_set():  # the user left: do not pay for the check
        return
    yield {
        "type": "written",
        "index": index,
        "count": len(found),
        "unmatched": _unmatched(source, found) if found else [],
    }
    if not found:
        return
    written = "\n\n".join(f"## {p.title}\n\n{p.body}" for p in found)
    omitted: list[str] = []
    unchecked = False
    try:
        missing = _ask_json(s, CHECK, f"SOURCE:\n{source}\n\nNOTES:\n{written}")
        omitted = [m.strip() for m in missing if isinstance(m, str) and m.strip()]
    except ai.AIError:  # the notes are good; only the check did not work
        unchecked = True
    yield {"type": "check", "index": index, "omitted": omitted, "unchecked": unchecked}


TEXT_TYPES = {".txt", ".md", ".markdown"}


IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp"}


def _image_mime(raw: bytes) -> str | None:
    """The type of an image from its first bytes (the file name can lie), None for anything else."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def _image_blocks(raw: bytes, s: dict[str, object]) -> list[docx.Block]:
    """The text of an image as blocks, read by the vision model (one call, before the notes are written)."""
    if not ai.vision_model(s):
        raise docx.BadFile("no_vision")
    mime = _image_mime(raw)
    if mime is None:
        raise docx.BadFile("not_image")
    return textfile.extract(
        ai.read_image(s, raw, mime).encode()
    )  # "empty" when no text


def _blocks(raw: bytes, name: str, s: dict[str, object]) -> list[docx.Block]:
    """The blocks of a file, read by the parser of its type (the extension of `name`)."""
    kind = PurePath(name).suffix.lower()
    if kind == ".docx":
        return docx.extract(raw)
    if kind in TEXT_TYPES:
        return textfile.extract(raw)
    if kind in IMAGE_TYPES:
        return _image_blocks(raw, s)
    if kind == ".pdf":
        return pdf.extract(
            raw,
            MAX_TEXT,
            (lambda image, mime: ai.read_image(s, image, mime))
            if ai.vision_model(s)
            else None,
        )
    raise docx.BadFile("unsupported")


def prepare(raw: bytes, s: dict[str, object], name: str) -> list[list[docx.Block]]:
    """The parts of a file (`name` tells its type), after every check that can fail before any model call.
    Raises ai.AIError (AI off or not configured) and docx.BadFile."""
    ai.ready(s)
    blocks = _blocks(raw, name, s)
    if sum(len(b.text) for b in blocks) > MAX_TEXT:
        raise docx.BadFile("too_large")
    return windows(blocks)


def run(
    s: dict[str, object], parts: list[list[docx.Block]], only: set[int] | None = None
) -> Iterator[dict[str, object]]:
    """Events as they happen: `start` (part count and labels), then for each part `note`s while the
    model writes, `written`, `check` or `error` (see `_part_events`; events of different parts are
    mixed, every one carries its part `index`), then `done`. `only` runs just those parts again.
    Nothing is saved."""
    todo = [i for i in range(len(parts)) if only is None or i in only]
    yield {
        "type": "start",
        "total": len(parts),
        "labels": [_label(p) for p in parts],
        "parts": todo,
    }
    stop = threading.Event()
    known = vocabulary()
    events: queue.Queue[dict[str, object] | None] = queue.Queue()

    def work(i: int) -> None:
        try:
            for event in _part_events(s, i, parts[i], stop, known):
                events.put(event)
        except Exception:  # noqa: BLE001  a bug in one part must not leave the stream waiting forever
            events.put(
                {
                    "type": "error",
                    "index": i,
                    "code": "failed",
                    "detail": "unexpected error",
                }
            )
        finally:
            events.put(None)  # this part is over

    with ThreadPoolExecutor(WORKERS) as pool:
        try:
            for i in todo:
                pool.submit(work, i)
            running = len(todo)
            while running:
                event = events.get()
                if event is None:
                    running -= 1
                else:
                    yield event
        finally:
            stop.set()  # the client went away: parts stop writing and make no further call
    yield {"type": "done"}
