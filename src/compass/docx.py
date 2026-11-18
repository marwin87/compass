"""Read the text of a MS Word (.docx) file: a zip with `word/document.xml`. Stdlib only.

Only structure that survives as Markdown is kept: headings, list items, tables, plain paragraphs.
The original file is never stored.
"""

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_XML = 30 * 1024 * 1024  # uncompressed size of document.xml (zip-bomb guard)
HEADING = re.compile(r"^(?:Heading|Nag[łl]ówek)\s?(\d)$", re.IGNORECASE)


class BadFile(Exception):
    """code: not_docx | not_text | empty | too_large | unsupported."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Block:
    heading: int  # 0 = not a heading, else the level (1 is the top)
    text: str  # Markdown; for a heading, the bare title without `#`


def _text(node: ET.Element) -> str:
    parts: list[str] = []
    for el in node.iter():
        if el.tag == f"{W}t" and el.text:
            parts.append(el.text)
        elif el.tag in (f"{W}tab", f"{W}br"):
            parts.append(" ")
    return " ".join("".join(parts).split())


def _paragraph(p: ET.Element) -> Block | None:
    text = _text(p)
    if not text:
        return None
    style = p.find(f"{W}pPr/{W}pStyle")
    name = style.get(f"{W}val", "") if style is not None else ""
    if name.lower() == "title":
        return Block(1, text)
    if m := HEADING.match(name):
        return Block(int(m.group(1)), text)
    if p.find(f"{W}pPr/{W}numPr") is not None:
        return Block(0, f"- {text}")
    return Block(0, text)


def _table(tbl: ET.Element) -> Block | None:
    rows = [
        [_text(c).replace("|", "\\|") for c in tr.findall(f"{W}tc")]
        for tr in tbl.findall(f"{W}tr")
    ]
    rows = [r for r in rows if any(r)]
    if not rows:
        return None
    width = max(len(r) for r in rows)
    lines = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in rows]
    lines.insert(1, "|" + " --- |" * width)
    return Block(0, "\n".join(lines))


def extract(raw: bytes) -> list[Block]:
    """The blocks of a .docx file in reading order. Raises BadFile."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.getinfo("word/document.xml").file_size > MAX_XML:
                raise BadFile("too_large")
            xml = z.read("word/document.xml")
        # ponytail: stdlib ET (expat guards against entity blow-up); defusedxml if files ever come from strangers
        body = ET.fromstring(xml).find(f"{W}body")
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        raise BadFile("not_docx") from None
    if body is None:
        raise BadFile("not_docx")
    blocks: list[Block] = []
    for child in body:
        found = (
            _paragraph(child)
            if child.tag == f"{W}p"
            else _table(child)
            if child.tag == f"{W}tbl"
            else None
        )
        if found:
            blocks.append(found)
    if not blocks:
        raise BadFile("empty")
    return blocks
