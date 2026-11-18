"""Read a plain text or Markdown file (.txt, .md) into the same blocks as a Word file.

Paragraphs are separated by blank lines; a Markdown heading line (`# Title`) is a heading block; a
fenced code block stays one block even when it contains blank lines. The text is kept as written, so
Markdown lists, tables and code reach the model as they are.
"""

import re
import unicodedata

from compass.docx import BadFile, Block

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")


def decode(raw: bytes) -> str:
    """UTF-8 (with or without a BOM), else Windows-1250 (old Polish files), as composed (NFC) text.
    Binary data is refused."""
    if b"\x00" in raw:
        raise BadFile("not_text")
    for encoding in ("utf-8-sig", "cp1250"):
        try:
            # NFC: macOS can write "ó" as "o" + an accent mark, which would be a different tag or title
            return unicodedata.normalize("NFC", raw.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise BadFile("not_text")


def extract(raw: bytes) -> list[Block]:
    """The blocks of a text file in reading order. Raises BadFile."""
    blocks: list[Block] = []
    lines: list[str] = []
    fenced = False

    def flush() -> None:
        text = "\n".join(lines).strip()
        if text:
            blocks.append(Block(0, text))
        lines.clear()

    for line in decode(raw).splitlines():
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            if not line.strip():
                flush()
                continue
            if m := HEADING.match(line):
                flush()
                if m.group(2):
                    blocks.append(Block(len(m.group(1)), m.group(2)))
                continue
        lines.append(line)
    flush()
    if not blocks:
        raise BadFile("empty")
    return blocks
