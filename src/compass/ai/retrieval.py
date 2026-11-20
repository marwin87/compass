"""Retrieval for the chat: which excerpts of the notes go to the model with a question.

Two ranked lists are merged (reciprocal rank fusion): the chunks closest in meaning (vector index,
only when an embedding model is set) and the best chunk of every note the keyword search finds. Then
the result is cut to a size the model gets: few notes, few chunks per note, a character budget. Without
an embedding model, or before the index is built, the keyword list alone is used. Read only: the search
index is never touched, and a question's text is never logged.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass

from compass import ai, notes
from compass.ai import chunks
from compass.search import fold, words

log = logging.getLogger(
    "uvicorn.error"
)  # timings only, never the question or note text

CONTEXT_CHARS = 12_000  # all excerpts together
MAX_NOTES = 8
PER_NOTE = 2  # chunks of one note
VECTOR_HITS = 20
KEYWORD_NOTES = 10
RRF_K = 60  # the usual constant: a rank matters less the further down it is
MIN_WORD = 3  # "a", "w", "co" say nothing; the keyword search ORs its words, so they only add noise


@dataclass(frozen=True)
class Excerpt:
    note_id: int
    title: str
    text: str


def _best_chunk(note: notes.Note, tokens: list[str]) -> tuple[int, str]:
    """The chunk of the note that holds most of the question's words (the first one on a tie)."""
    pieces = chunks.split(note.title, note.body)
    hits = [sum(fold(p).count(t) for t in tokens) for p in pieces]
    best = hits.index(max(hits))
    return best, pieces[best]


def retrieve(
    s: dict[str, object], question: str, history: list[str] | None = None
) -> list[Excerpt]:
    """Excerpts for `question`, best first. `history` holds the user's earlier questions of the
    conversation: the last one is added to the search so a follow-up ("and when?") still finds notes.
    Raises AIError when the embedding call fails."""
    query = " ".join([*(history or [])[-1:], question])
    tokens = [w for w in words(query) if len(w) >= MIN_WORD]

    found: dict[tuple[int, int], tuple[str, str]] = {}  # (note, chunk) -> (title, text)
    ranked: list[list[tuple[int, int]]] = []

    t0 = time.perf_counter()
    embed_ms = search_ms = 0.0
    if ai.embed_model(s) and query.strip():
        (vector,) = ai.embed(s, [query])
        embed_ms = (time.perf_counter() - t0) * 1000
        hits = chunks.search(s, vector, VECTOR_HITS)
        search_ms = (time.perf_counter() - t0) * 1000 - embed_ms
        titles: dict[int, str] = {}
        for note_id, idx, text, _score in hits:
            if note_id not in titles and (note := notes.get_note(note_id)):
                titles[note_id] = note.title
            found[(note_id, idx)] = (titles.get(note_id, ""), text)
        ranked.append([(n, i) for n, i, _t, _c in hits])

    t1 = time.perf_counter()
    if tokens:
        keyword: list[tuple[int, int]] = []
        for note in notes.list_notes(" ".join(tokens))[:KEYWORD_NOTES]:
            idx, text = _best_chunk(note, tokens)
            found.setdefault((note.id, idx), (note.title, text))
            keyword.append((note.id, idx))
        ranked.append(keyword)

    log.info(
        "chat retrieve: embed %.0f ms, vector search %.0f ms, keyword %.0f ms",
        embed_ms,
        search_ms,
        (time.perf_counter() - t1) * 1000,
    )
    score: defaultdict[tuple[int, int], float] = defaultdict(float)
    for ranking in ranked:
        for rank, key in enumerate(ranking):
            score[key] += 1 / (RRF_K + rank)

    out: list[Excerpt] = []
    per_note: dict[int, int] = {}
    used = 0
    for key in sorted(score, key=lambda k: (-score[k], k)):
        note_id = key[0]
        title, text = found[key]
        if per_note.get(note_id, 0) >= PER_NOTE:
            continue
        if note_id not in per_note and len(per_note) >= MAX_NOTES:
            continue
        if used + len(text) > CONTEXT_CHARS:
            continue  # a smaller one further down may still fit
        out.append(Excerpt(note_id, title, text))
        per_note[note_id] = per_note.get(note_id, 0) + 1
        used += len(text)
    return out
