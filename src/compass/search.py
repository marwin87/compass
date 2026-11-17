"""Pure text helpers for search: folding, tokenising, typo tolerance, ranking.

No database access here; `notes.py` owns SQLite.
"""

import re
import unicodedata
from collections.abc import Collection, Iterable, Sequence

# Letters that NFKD does not split into "base letter + accent".
_EXTRA = str.maketrans({"ł": "l", "đ": "d", "ø": "o"})

# Field tiers (higher is better) and match exactness inside a tier.
TAG, TITLE, BODY = 3, 2, 1
EXACT, PREFIX, FUZZY = 2, 1, 0

MIN_FUZZY_LEN = 4  # shorter words are never "corrected" (sql, api, db...)
MAX_FUZZY_TERMS = 25  # per query word, closest first


def fold(text: str) -> str:
    """Lowercase and strip diacritics (also ł, đ, ø, ß) so 'Złożoność' -> 'zlozonosc'."""
    text = text.lower().replace("ß", "ss").translate(_EXTRA)
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def words(text: str) -> list[str]:
    """Folded word tokens; same split as FTS5's unicode61 (letters and digits)."""
    return re.findall(r"[^\W_]+", fold(text))


def _quality(
    token: str, field_words: Sequence[str], fuzzy: Collection[str]
) -> int | None:
    """Best way `token` matches one of the field's words, or None."""
    best: int | None = None
    for word in field_words:
        if word == token:
            return EXACT
        if word.startswith(token):
            quality = PREFIX
        elif word in fuzzy:
            quality = FUZZY
        else:
            continue
        best = quality if best is None else max(best, quality)
    return best


def rank_key(
    tokens: Sequence[str],
    title: str,
    body: str,
    tags: Sequence[str],
    fuzzy: dict[str, set[str]],
) -> tuple[int, int, int]:
    """Relevance of one note for a query, higher is better.

    (words matched, best field tier, exactness within that tier). Tiers: an exact tag
    (equal to the whole query or to one of its words) beats the title, which beats the body
    (non-exact tag words count as body). The caller appends the note id as the last tie-break.
    """
    folded_tags = {fold(t) for t in tags}
    whole_query_is_a_tag = " ".join(tokens) in folded_tags
    title_words, body_words = words(title), words(body)
    tag_words = [w for t in tags for w in words(t)]
    matched = 0
    best = (0, 0)
    for token in tokens:
        hits: list[tuple[int, int]] = []
        if whole_query_is_a_tag or token in folded_tags:
            hits.append((TAG, EXACT))
        no_fuzzy: set[str] = set()
        for tier, field in (
            (TITLE, title_words),
            (BODY, body_words),
            (BODY, tag_words),
        ):
            quality = _quality(token, field, fuzzy.get(token, no_fuzzy))
            if quality is not None:
                hits.append((tier, quality))
        if hits:
            matched += 1
            best = max(best, *hits)
    return (matched, best[0], best[1])


def edit_distance(a: str, b: str, limit: int) -> int | None:
    """Optimal string alignment distance (an adjacent swap is one edit), or None above `limit`."""
    if abs(len(a) - len(b)) > limit:
        return None
    before: list[int] | None = None
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        new = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            value = min(row[j] + 1, new[j - 1] + 1, row[j - 1] + (ca != cb))
            if before is not None and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                value = min(value, before[j - 2] + 1)
            new[j] = value
        if min(new) > limit:
            return None
        before, row = row, new
    return row[-1] if row[-1] <= limit else None


def fuzzy_terms(token: str, vocab: Iterable[str]) -> set[str]:
    """Vocabulary terms within the allowed number of typos of `token`.

    1 edit for words of 4-7 letters, 2 for 8+, none below 4 letters. The token itself is
    left out (exact and prefix matches already cover it).
    """
    if len(token) < MIN_FUZZY_LEN:
        return set()
    limit = 1 if len(token) < 8 else 2
    close: list[tuple[int, str]] = []
    for term in vocab:
        if term == token:
            continue
        distance = edit_distance(token, term, limit)
        if distance is not None:
            close.append((distance, term))
    close.sort()
    return {term for _, term in close[:MAX_FUZZY_TERMS]}
