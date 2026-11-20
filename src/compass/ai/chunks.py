"""The vector index of the notes (table `note_chunks`), the base of the chat's retrieval.

Derived data: each note is cut into chunks, every chunk gets one embedding, and a question is matched
by cosine similarity. It sits next to the search index (`notes_fts`) and never touches it. Saving or
deleting a note never calls the model: an edited note is simply *stale* (its digest or the embedding
model differs from the chunk rows) and `sync` embeds it later; a deleted note takes its chunks along
(`ON DELETE CASCADE`). The index is not exported; it is rebuilt from the notes.
"""

import math
import re
import sqlite3
from array import array
from collections.abc import Iterator

from compass import ai
from compass.db import connect
from compass.notes.summaries import digest

CHUNK_CHARS = 1200
BATCH = 32  # chunks per embeddings call
FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^#{1,6}\s")


def _sections(body: str) -> list[str]:
    """The body cut before every heading (a `#` inside a fenced code block is not one)."""
    sections: list[list[str]] = [[]]
    fenced = False
    for line in body.splitlines():
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced and HEADING.match(line) and any(sections[-1]):
            sections.append([])
        sections[-1].append(line)
    return ["\n".join(s).strip() for s in sections if any(x.strip() for x in s)]


def _pack(section: str) -> list[str]:
    """A section as pieces of at most CHUNK_CHARS: whole paragraphs, a longer paragraph cut by size."""
    pieces: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", section):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if current and len(current) + len(paragraph) + 2 > CHUNK_CHARS:
            pieces.append(current)
            current = ""
        while len(paragraph) > CHUNK_CHARS:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(paragraph[:CHUNK_CHARS])
            paragraph = paragraph[CHUNK_CHARS:]
        current = f"{current}\n\n{paragraph}" if current else paragraph
    return [*pieces, current] if current else pieces


def split(title: str, body: str) -> list[str]:
    """The chunks of a note, each starting with the title (a title alone is one chunk)."""
    pieces = [piece for section in _sections(body) for piece in _pack(section)]
    return [f"{title}\n\n{piece}" for piece in pieces] or [title]


def _pack_vec(vector: list[float]) -> bytes:
    """Unit length, as 32-bit floats: the dot product of two of them is their cosine."""
    norm = math.sqrt(math.sumprod(vector, vector)) or 1.0
    return array("f", (x / norm for x in vector)).tobytes()


def _unpack(blob: bytes) -> array[float]:
    vector: array[float] = array("f")
    vector.frombytes(blob)
    return vector


def _stale(conn: sqlite3.Connection, name: str) -> list[tuple[int, str, str, str]]:
    """(id, title, body, digest) of every note without chunks that match its text and the model."""
    current = {
        row[0]: row[1:]
        for row in conn.execute(
            "SELECT note_id, MIN(source_hash), MIN(model), MAX(source_hash), MAX(model) "
            "FROM note_chunks GROUP BY note_id"
        )
    }
    stale = []
    for note_id, title, body in conn.execute("SELECT id, title, body FROM notes"):
        wanted = digest(title, body)
        if current.get(note_id) != (wanted, name, wanted, name):
            stale.append((note_id, title, body, wanted))
    return stale


def status(s: dict[str, object]) -> dict[str, int]:
    """How many notes there are and how many of them are indexed with the current text and model."""
    conn = connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        stale = len(_stale(conn, ai.embed_model(s)))
    finally:
        conn.close()
    return {"total": total, "indexed": total - stale if ai.embed_model(s) else 0}


def clear() -> None:
    """Drop the whole index. It is derived data: the next question or "Build index" fills it again."""
    conn = connect()
    try:
        with conn:
            conn.execute("DELETE FROM note_chunks")
    finally:
        conn.close()


def sync(s: dict[str, object], limit: int | None = None) -> Iterator[dict[str, object]]:
    """Embed the stale notes (at most `limit`), newest first, and say how it goes: `start`, `progress`,
    `done` events, or `error` (an AIError, the index keeps what is already written). Raises AIError
    before the first event when AI is off or no embedding model is set."""
    ai.ready(s)
    name = ai.embed_model(s)
    if not name:
        raise ai.AIError("not_configured", "embedding model")
    conn = connect()
    try:
        todo = sorted(_stale(conn, name), reverse=True)[:limit]
        yield {"type": "start", "total": len(todo)}
        for done, (note_id, title, body, wanted) in enumerate(todo, 1):
            texts = split(title, body)
            try:
                vectors = [
                    v
                    for start in range(0, len(texts), BATCH)
                    for v in ai.embed(s, texts[start : start + BATCH])
                ]
            except ai.AIError as problem:
                yield {"type": "error", "code": problem.code, "detail": problem.detail}
                return
            try:
                with conn:
                    conn.execute(
                        "DELETE FROM note_chunks WHERE note_id = ?", (note_id,)
                    )
                    conn.executemany(
                        "INSERT INTO note_chunks(note_id, idx, text, vec, model, source_hash) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        [
                            (note_id, i, t, _pack_vec(v), name, wanted)
                            for i, (t, v) in enumerate(zip(texts, vectors, strict=True))
                        ],
                    )
            except (
                sqlite3.IntegrityError
            ):  # the note was deleted while the model worked
                pass
            yield {"type": "progress", "done": done, "total": len(todo)}
        yield {"type": "done"}
    finally:
        conn.close()


def search(
    s: dict[str, object], query: list[float], k: int
) -> list[tuple[int, int, str, float]]:
    """The `k` chunks closest to `query` as (note id, chunk number, text, cosine), best first. Only chunks
    made by the current embedding model count. ponytail: brute force over every chunk (fine to about
    50 000); a vector extension if it ever gets slow."""
    unit = _unpack(_pack_vec(query))
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT note_id, idx, text, vec FROM note_chunks WHERE model = ?",
            (ai.embed_model(s),),
        ).fetchall()
    finally:
        conn.close()
    scored = [
        (note_id, idx, text, math.sumprod(unit, vec))
        for note_id, idx, text, blob in rows
        if len(vec := _unpack(blob)) == len(unit)
    ]
    scored.sort(key=lambda r: r[3], reverse=True)
    return scored[:k]
