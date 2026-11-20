"""Read a PDF with `pypdf` (pure Python text, Pillow for pictures). The original file is never stored.

One block per page that has text, in page order, no headings: a PDF has no reliable heading structure, so
none is invented (the model that writes the notes finds the topics). Lines that repeat on most pages
(running headers and footers, "Page 3 of 9") are dropped.

A page with (almost) no text is a scan or a picture of text: its pictures are read by the vision model
(`read`, one call each, a few at a time) and their text is the page. Pictures on a page that already has
text are not read (logos, photos), and nothing is rendered, so a drawing made of vector shapes stays
unread. Not read at all: encrypted files. Columns and tables come out as plain lines, in the order pypdf
finds them.
"""

import io
import re
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from pypdf import PdfReader
from pypdf.errors import DependencyError, PyPdfError

from compass.importing.docx import BadFile, Block

REPEATED_PAGES = 3  # a line must be on at least this many pages, and on half of all pages, to be a header
MIN_PAGE_TEXT = 40  # characters; a page with less is read as a picture
MIN_SIDE = 200  # pixels; smaller pictures are icons and rules, not pages of text
MAX_SIDE = 2000  # pixels; a bigger picture is scaled down before it goes to the model
MAX_PICTURES = (
    10  # pictures read by the vision model in one file; more is refused, not half read
)
READERS = 4  # pictures read side by side

Read = Callable[
    [bytes, str], str
]  # (image bytes, mime) -> its text, "" when it has none


def _key(line: str) -> str:
    """A line with its numbers blanked, so "Page 1 of 9" and "Page 2 of 9" count as one line."""
    return re.sub(r"\d+", "#", line.strip())


def _without_repeats(pages: list[str]) -> list[str]:
    """The pages without the lines that repeat on most of them. ponytail: naive, a line seen on at least
    3 pages and on at least half of all pages; a smarter header detector only if real files need it."""
    if len(pages) < REPEATED_PAGES:
        return pages
    seen = Counter(
        key
        for text in pages
        for key in {_key(line) for line in text.splitlines() if line.strip()}
    )
    repeated = {
        k for k, n in seen.items() if n >= REPEATED_PAGES and n * 2 >= len(pages)
    }
    return [
        "\n".join(line for line in text.splitlines() if _key(line) not in repeated)
        for text in pages
    ]


def _pictures(page: object) -> list[bytes]:
    """The pictures of a page big enough to hold text, as JPEG bytes of at most MAX_SIDE pixels."""
    out: list[bytes] = []
    try:
        for item in page.images:  # type: ignore[attr-defined]
            image = item.image
            if min(image.size) < MIN_SIDE:
                continue
            image = image.convert("RGB")
            image.thumbnail((MAX_SIDE, MAX_SIDE))
            buf = io.BytesIO()
            image.save(buf, "JPEG", quality=85)
            out.append(buf.getvalue())
    except Exception:  # noqa: BLE001  a picture pypdf cannot decode is skipped, the rest of the file is read
        return out
    return out


def _read_pages(raw: bytes, limit: int) -> tuple[list[str], dict[int, list[bytes]]]:
    """The text of each page, and the pictures of the pages without text (page -> pictures).
    Raises BadFile: `encrypted`, `too_large` or `not_pdf`."""
    pages: list[str] = []
    pictures: dict[int, list[bytes]] = {}
    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted and not reader.decrypt(""):
            raise BadFile("encrypted")  # a password is needed
        size = 0
        for number, page in enumerate(reader.pages):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:  # noqa: BLE001  one odd page must not lose the file
                text = ""
            if len(text) < MIN_PAGE_TEXT and (found := _pictures(page)):
                pictures[number] = found
            pages.append(text)
            size += len(text)
            if size > limit:
                raise BadFile("too_large")
    except BadFile:
        raise
    except DependencyError:  # an AES-encrypted file needs a package we do not install
        raise BadFile("encrypted") from None
    except (PyPdfError, ValueError, KeyError, TypeError, OSError, RecursionError):
        raise BadFile("not_pdf") from None
    return pages, pictures


def _read_pictures(
    pages: list[str], pictures: dict[int, list[bytes]], read: Read
) -> None:
    """Add the text `read` finds in the pictures to their pages. Raises BadFile `too_many_images`."""
    if sum(len(p) for p in pictures.values()) > MAX_PICTURES:
        raise BadFile("too_many_images")
    flat = [(n, p) for n, found in pictures.items() for p in found]
    with ThreadPoolExecutor(READERS) as pool:
        texts = list(pool.map(lambda item: read(item[1], "image/jpeg"), flat))
    for (n, _), text in zip(flat, texts, strict=True):
        pages[n] = f"{pages[n]}\n\n{text}".strip()


def extract(raw: bytes, limit: int, read: Read | None = None) -> list[Block]:
    """The text blocks of a PDF, one per page that has any. `read` reads a picture with the vision model
    (None: no vision model, pictures are not read). Raises BadFile: `not_pdf`, `encrypted`, `too_large`
    (more than `limit` characters, found without reading the rest), `too_many_images` (more than
    MAX_PICTURES pictures to read), `no_vision` (only pictures, and no vision model) or `empty` (no text).
    Raises ai.AIError through `read`."""
    if b"%PDF-" not in raw[:1024]:
        raise BadFile("not_pdf")
    pages, pictures = _read_pages(raw, limit)
    if pictures and read is not None:
        _read_pictures(pages, pictures, read)
    blocks = [
        Block(0, text.strip()) for text in _without_repeats(pages) if text.strip()
    ]
    if not blocks:
        raise BadFile("no_vision" if pictures and read is None else "empty")
    return blocks
