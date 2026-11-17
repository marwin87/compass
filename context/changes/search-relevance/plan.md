# S-06 search-relevance Implementation Plan

## Overview
Make search return the most relevant notes first and forgive typos and missing Polish letters, as the PRD's business rule demands: a title match ranks above a body-only match, an exact tag ranks above a plain word, and `zlozonosc` finds "złożoność". Response time must stay a fraction of a second.

## Current State Analysis
- `src/compass/db.py`: `SCHEMA` creates `meta`, `notes`, `tags`, `note_tags` and an FTS5 **external-content** index `notes_fts(title, body)` (`content='notes'`). `connect()` enables foreign keys and runs the schema on every connection.
- `src/compass/notes.py`: `match_query(q)` builds `"word"* OR ...`; `list_notes(q, tags)` filters by that match and the tag AND-filter and orders by `id DESC` (cap 50). Create/update/delete keep the FTS index in step using the external-content `'delete'` command; tags are saved by `_save_tags` and cleaned by `_drop_unused_tags`.
- Tags are not in the text index (S-05 left that to this slice). A test, `test_text_search_does_not_match_tag_words`, pins today's behaviour and will be flipped.
- `src/compass/api.py` and `src/compass/page.py` need no change: `GET /api/notes?q=&tag=` already feeds the list; only the order and the set of matches change.
- FTS5 and `fts5vocab` are available in the local SQLite and in the Docker image (SQLite 3.40).

## Desired End State
Typing a query returns notes ranked by this key (all descending):
1. number of query words matched (anywhere: tag, title, body, exactly, as a prefix, or fuzzily);
2. best field tier: **exact tag** (a tag equals the whole folded query or one of its words) > **title** > **body** (a non-exact tag word counts as body tier);
3. exactness within that tier: exact word > prefix > typo;
4. newer note first (higher id).
Matching is case- and diacritic-insensitive on both sides (`ł→l`, `ą→a`, ...). Typos are tolerated: 1 edit for words of 4–7 letters, 2 for 8+, none below 4 letters (adjacent swaps count as 1 edit). Fuzzy hits are always included but rank below exact/prefix hits in the same field. The empty query still lists everything newest first; the tag filter keeps AND semantics and combines with the text.

### Key Discoveries
- FTS5's `unicode61` strips most accents but not `ł`, so folding must be explicit and applied to both indexed text and the query.
- An external-content index cannot hold folded text different from `notes`, so the index becomes a regular FTS5 table `notes_fts(title, body, tags)` holding folded text, `rowid` = note id; `DELETE ... WHERE rowid = ?` plus `INSERT` replaces the fragile `'delete'`-with-old-values trick.
- The vocabulary for typo candidates comes from an `fts5vocab` table over that index (`'row'` type), so no separate dictionary is stored.
- Existing databases hold the old index under the same name: a version flag in `meta` drives a one-off rebuild at connect time, before any query.

## What We're NOT Doing
Highlighting why a note matched, synonyms/stemming (Polish inflection), phrase or `AND` operators in queries, per-user tuning of weights, spell-suggest ("did you mean"), pagination beyond the 50-result cap, folding of the tag filter values (tags keep their stored form), a typo-fix for words under 4 letters, caching the vocabulary.

## Implementation Approach
- `src/compass/search.py` (new, no DB access): `fold(text)`, `words(text)`, `fuzzy_terms(token, vocab)` with a bounded Damerau-Levenshtein and a length pre-filter, and the ranking key. `notes.py` stays the only module talking to SQLite.
- Index writes go through one helper `_index(conn, note_id, title, body, tags)`: delete the row, insert folded title/body/tags; called by create, update (also when only tags change) and delete (row removal only).
- Search = (1) fold and tokenise the query; (2) expand each token with fuzzy vocabulary terms; (3) FTS candidate query `ORDER BY bm25(notes_fts, 10, 1, 20) LIMIT 200` combined with the tag filter; (4) re-rank the candidates in Python with the key above and return the top 50.

## Critical Implementation Details
- **Migration ordering**: `connect()` must run the index check inside a `BEGIN IMMEDIATE` transaction and re-read `meta.fts_version` there, so two concurrent first connections do not both rebuild. The old external-content `notes_fts` and any vocab table must be dropped before the new ones are created; schema creation for `notes_fts` is therefore taken out of the plain `SCHEMA` script.
- **Candidate cap**: the 200-candidate cut is by weighted bm25, so a matching exact-tag or title note must reliably outrank body-only matches in that cut; the weights (title 10, tags 20, body 1) exist for this and are covered by a test with many body-only matches.
- **Performance**: vocabulary scan (all terms, length-filtered) is the fuzzy cost; the 5000-note timing test must include a typo query and stay well under the PRD budget.

## Phase 1: Folded index with tags

### Changes Required
#### 1. `src/compass/search.py` (new)
**Intent**: Text folding and tokenising shared by indexing and querying.
**Contract**: `fold(text: str) -> str` lowercases, maps `ł→l`, `đ→d`, `ø→o`, `ß→ss`, then NFKD-decomposes and drops combining marks; `words(text: str) -> list[str]` returns `\w+` tokens of the folded text. Pure functions, typed.
#### 2. `src/compass/db.py`
**Intent**: Replace the external-content index with a regular folded one and migrate old databases.
**Contract**: `SCHEMA` no longer creates `notes_fts`. After the schema script, `connect()` calls an index check: inside `BEGIN IMMEDIATE`, if `meta.fts_version != '2'`: drop `notes_vocab` and `notes_fts` if present, create `notes_fts` as `fts5(title, body, tags)`, create `notes_vocab` as `fts5vocab(notes_fts, 'row')`, refill the index from `notes` and their tags (folded), set `fts_version = '2'`. A second connect does not rebuild.
#### 3. `src/compass/notes.py`
**Intent**: Keep the folded index in step and make tags searchable.
**Contract**: `_index(conn, note_id, title, body, tags)`; `create_note`, `update_note` (also after tag changes) and `delete_note` use it; the `'delete'`-command code is removed. `match_query(q)` folds the query. Result order is still newest first in this phase. `COLUMNS`, API and page are unchanged.
#### 4. `tests/`
**Intent**: Pin folding, tag searchability and migration.
**Contract**: `fold` cases (`złożoność→zlozonosc`, `ŻÓŁĆ→zolc`, `Ą`, plain ASCII, empty); both directions (`zlozonosc` finds `złożoność`, `złożoność` finds a note typed `zlozonosc`); a word that appears only in a tag is found by the text search (flip `test_text_search_does_not_match_tag_words`); edit and delete leave no stale words (title, body and tags); migration: a database built with the old external-content index and notes with Polish text opens, searches correctly and has `fts_version = '2'`, and a second connect leaves the index untouched; the S-02..S-05 tests and the timing test keep passing (the timing test writes `notes_fts(rowid, title, body, tags)` directly).

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- `uv run mypy src tests`
#### Manual Verification
- Against a copy of a real database with existing notes: after starting the app, existing notes are still found, `zlozonosc` finds a note titled "Złożoność", and a word typed only as a tag finds its note

---

## Phase 2: Relevance ranking

### Changes Required
#### 1. `src/compass/search.py`
**Intent**: The ranking key as a pure, testable function.
**Contract**: `rank_key(query_tokens, full_query, note_fields, fuzzy) -> tuple[int, int, int]` (matched words, best tier, exactness) per the key above, where tiers are exact tag = 3, title = 2, body or non-exact tag word = 1 and exactness is exact word = 2, prefix = 1, typo = 0; a note's final sort key appends `id`. Constants for tiers and weights live at the top of the module.
#### 2. `src/compass/notes.py`
**Intent**: Retrieve candidates and order them.
**Contract**: `list_notes(q, tags)`: for a non-empty query, fetch up to 200 candidate ids with `ORDER BY bm25(notes_fts, 10.0, 1.0, 20.0)`, apply the tag AND-filter, load title/body/tags of the candidates, sort by the key (descending, then `id` descending) and return the first 50. An empty query keeps the newest-first listing with the tag filter. Fuzzy sets are empty in this phase.
#### 3. `tests/test_notes.py`
**Intent**: One test per ranking rule from the plan and the PRD.
**Contract**: title above body-only; exact tag above a plain word in the title; exact tag equal to the whole multi-word query; two matched words above one word in a title; exactness inside a tier (exact word > prefix); equal scores resolve newest first; notes found only through a tag appear; the tag filter still ANDs with the ranked text search; an exact-tag note among 300 body-only matches is first (candidate-cut safety).

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
#### Manual Verification
- With a handful of realistic notes in the browser, the order matches the rules: tagged note first, then title hits, then body hits; two-word queries put notes with both words first

---

## Phase 3: Typo tolerance

### Changes Required
#### 1. `src/compass/search.py`
**Intent**: Find vocabulary terms close to a query word.
**Contract**: `fuzzy_terms(token: str, vocab: Iterable[str]) -> set[str]`: nothing for tokens under 4 letters; max edits 1 for 4–7 letters, 2 for 8+; Damerau-Levenshtein (optimal string alignment) with early exit; terms whose length differs by more than the limit are skipped; the token itself is excluded (it is already matched by prefix).
#### 2. `src/compass/notes.py`
**Intent**: Include fuzzy matches in the candidate query and the ranking.
**Contract**: the vocabulary is read from `notes_vocab` (`SELECT DISTINCT term`) per search; each fuzzy term is added to the FTS query as an exact quoted term; in the ranking a note's match on a fuzzy term has exactness 0 and still counts as a matched word, so typo hits sit below exact and prefix hits within the same field.
#### 3. `tests/`
**Intent**: Cover tolerance, limits and speed.
**Contract**: unit tests for `fuzzy_terms` (substitution, deletion, insertion, adjacent swap, 4-7 vs 8+ letters, under 4 letters untouched); `indkes` finds "indeks", `zlozonsoc` finds "złożoność"; a typo in the title ranks below an exact title hit and above body-only exact hits only by the field rule (title typo above body exact); `sql` (3 letters) does not fuzzy-match `sqr`; the 5000-note timing test also runs a typo query and stays under the budget (assert well below 0.5 s).

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
#### Manual Verification
- Typing `indkes`, `zlozonosc` and a one-letter typo of a longer word finds the intended notes; results appear without visible delay while typing
- Exact and tagged notes stay above typo hits
- Search still works after `docker compose down` / `up --build` (migration on the container's database)

## Testing Strategy
Pure-function tests for `fold`, fuzzy distance and the ranking key; API tests for each ordering rule and for the migration; the existing timing test extended with a typo query; manual checks in the browser for feel and order.

## Performance Considerations
Per search: one FTS query limited to 200 candidates, one vocabulary read, a length-filtered edit-distance pass over the vocabulary (cost grows with the number of distinct terms; fine for the MVP's data volume), and Python ranking of at most 200 notes. If the vocabulary grows large, cache it or switch to a trigram prefilter (not planned).

## Migration Notes
First connect after deployment rebuilds the index once (cost proportional to notes). The old external-content index is dropped; note data in `notes`, `tags` and `note_tags` is untouched, so rolling the code back leaves the old index missing but `CREATE ... IF NOT EXISTS` in the old schema would recreate it empty: a rollback needs a manual `INSERT INTO notes_fts(notes_fts) VALUES('rebuild')`.

## Open Risks & Assumptions
- The 200-candidate cut by weighted bm25 could in theory drop a relevant note when more than 200 notes match; weights and a test reduce this, and the 50-result cap already limits the list.
- Polish inflection ("indeksy" vs "indeksów") is covered only by prefix/typo matching, not stemming.
- Ranking constants (weights, edit limits, cap) are guesses to be tuned with real notes; the roadmap's "how is relevant tuned beyond the three rules" is answered by the key above and can be revisited.
- Rollback needs a manual index rebuild (see Migration Notes).

## References
- PRD "Business Logic", FR-007, FR-008; NFR response time; roadmap S-06
- `src/compass/db.py`, `src/compass/notes.py`, `tests/test_notes.py`

## Progress

### Phase 1: Folded index with tags
#### Automated
- [x] 1.1 `uv run pytest` passes
- [x] 1.2 ruff check and format check pass
- [x] 1.3 mypy strict passes
#### Manual
- [x] 1.4 On a copy of a real database: old notes still found, `zlozonosc` finds "Złożoność", tag-only words find notes

### Phase 2: Relevance ranking
#### Automated
- [x] 2.1 `uv run pytest` passes
- [x] 2.2 ruff, format check and mypy pass
#### Manual
- [x] 2.3 Order in the browser follows the rules (tag, title, body; two-word queries first)

### Phase 3: Typo tolerance
#### Automated
- [x] 3.1 `uv run pytest` passes (including the typo timing test)
- [x] 3.2 ruff, format check and mypy pass
- [x] 3.3 `docker build -t compass:dev .` passes
#### Manual
- [x] 3.4 `indkes`, `zlozonosc` and a one-letter typo find the intended notes without visible delay
- [x] 3.5 Exact and tagged notes stay above typo hits
- [x] 3.6 Search works after `down`/`up --build` (migration in the container)
