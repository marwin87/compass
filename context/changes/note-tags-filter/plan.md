# S-05 note-tags-filter Implementation Plan

## Overview
A logged-in user can attach tags to a note and narrow the list to notes that carry chosen tags. This completes US-01 (create a note with tags, find it by keyword) and FR-006/FR-008. Tag matching inside the text search and relevance ranking stay in S-06.

## Current State Analysis
- `src/compass/db.py`: `SCHEMA` creates `meta`, `notes`, FTS5 `notes_fts(title, body)`; `connect()` runs `executescript(SCHEMA)`; no `PRAGMA foreign_keys`.
- `src/compass/notes.py`: `Note(id, title, body, created_at)`, `create_note`, `get_note`, `list_notes(q)` (FTS prefix, any word, newest first, cap 50), `update_note`, `delete_note` (both keep the FTS index in step inside `BEGIN IMMEDIATE`).
- `src/compass/api.py`: `NoteIn(title, body)`, `/api/notes` POST/GET/GET{id}/PUT{id}/DELETE{id}; the guard returns 401 JSON for anonymous `/api/*`.
- `src/compass/page.py`: one HTML page; add form (`#add`), note view (`#read`) with edit/delete flows, search box and results list; all note text via `textContent`.
- Tests: `tests/test_notes.py` (API behaviour, 5000-note timing test), `tests/conftest.py` (`authed` fixture, env set unconditionally).

## Desired End State
Notes carry tags (lowercase, normalised). `POST`/`PUT` accept `tags`, every note response includes `tags`. `GET /api/notes?q=&tag=a&tag=b` returns notes that match the text (if any) AND carry every listed tag. `GET /api/tags` returns `[{name, count}]` for tags in use. The page shows a tag bar with counts (click toggles the filter), tags on results and in the note view, and a "Tagi (po przecinku)" field with clickable existing-tag suggestions in the add and edit forms.

### Key Discoveries
- Existing databases need no migration of `notes`: new tables are `CREATE ... IF NOT EXISTS`.
- SQLite foreign keys are off by default per connection; cascades only work after `PRAGMA foreign_keys = ON` in `connect()`.
- A native `<datalist>` completes the whole field value, not each comma-separated item, so it cannot suggest after the first comma; suggestions are rendered as clickable buttons that append a tag instead.
- The FTS index stays untouched (tags are not indexed), so S-02/S-03/S-04 behaviour and the 5000-note timing test are unaffected.

## What We're NOT Doing
Tag rename/merge/delete management, matching tag words in the text search or ranking by tag (S-06), diacritics folding of tags, tag colours, OR filtering, chip-style tag input, a `#tag` query syntax, tag order preserved from input (tags are listed alphabetically).

## Implementation Approach
- Schema: `tags(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)` and `note_tags(note_id REFERENCES notes ON DELETE CASCADE, tag_id REFERENCES tags ON DELETE CASCADE, PRIMARY KEY(note_id, tag_id))` plus an index on `tag_id`; `connect()` enables foreign keys.
- Normalisation lives in one function: split already done by the client (list of strings); each tag is stripped, lowercased and has inner whitespace collapsed; empties dropped; duplicates removed; at most 10 tags per note, each 1..30 characters and without commas, otherwise 422.
- `create_note`/`update_note` write the tag set in the same transaction as the note (update replaces the set); after update and delete, tags without notes are deleted in that same transaction.
- `list_notes(q, tags)` adds the AND-all-tags condition (`GROUP BY note_id HAVING COUNT(DISTINCT name) = n`) to the existing query; the filter values are normalised like stored tags. Notes are loaded first, then their tags in one extra query.

## Phase 1: Tags in data and API

### Changes Required
#### 1. `src/compass/db.py`
**Intent**: Add the tag tables and make cascades work.
**Contract**: `SCHEMA` gains `tags`, `note_tags` and `note_tags_tag` index (all `IF NOT EXISTS`); `connect()` runs `PRAGMA foreign_keys = ON` for every connection.
#### 2. `src/compass/notes.py`
**Intent**: Store, return and filter tags.
**Contract**: `Note` gains `tags: list[str]` (alphabetical). `normalize_tags(raw: list[str]) -> list[str]` (raises `ValueError` on limit violations). `create_note(title, body, tags)`, `update_note(id, title, body, tags)` (replaces the set, removes now-unused tags), `delete_note` (cascade plus unused-tag cleanup), `list_notes(q="", tags=())`, `get_note` include tags. `list_tags() -> list[TagCount]` returns `name`, `count` ordered by count desc, name asc.
#### 3. `src/compass/api.py`
**Intent**: Expose tags.
**Contract**: `NoteIn` gains `tags: list[str] = []` (validated via `normalize_tags`, violations are 422); `GET /api/notes` takes repeatable `tag` query parameters; `GET /api/tags` returns `[{"name", "count"}]`. `PUT` without `tags` clears the tags (full replacement, documented).
#### 4. `tests/`
**Intent**: Pin the tag behaviour, including cleanup and cascade.
**Contract**: normalisation (case, outer and inner whitespace, duplicates, empties dropped, `SQL`/`sql` is one tag, limits give 422); create/get/list return normalised, sorted tags; update replaces tags and clearing works; filter by one tag, by two tags (AND), tag plus text, unknown tag returns nothing, filter value normalised (`SQL` finds `sql`); `GET /api/tags` counts and ordering; a tag unique to a deleted/edited note disappears from `GET /api/tags` and from the `tags` table while a shared tag survives; deleting a note leaves no `note_tags` rows; a database created with the old schema (no tag tables) works after `connect()`; anonymous `GET /api/tags` is 401; existing S-02/S-03/S-04 tests and the timing test still pass.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- `uv run mypy src tests`
#### Manual Verification
- With `curl` and a session cookie: create notes with tags, list `GET /api/tags`, filter with one and two `tag=` parameters

---

## Phase 2: Tags in the UI

### Changes Required
#### 1. `src/compass/page.py`
**Intent**: Let the user tag notes and filter by tag.
**Contract**: add and edit forms get a "Tagi (po przecinku)" text input; the client splits on commas and sends a list. Under each field a row of existing-tag buttons (from `GET /api/tags`, at most 30) appends that tag if not already present. Below the search box a tag bar of `#name (count)` buttons toggles membership in a `selected` set; selected tags are highlighted and sent as repeated `tag` parameters with the text query; the list reloads on every toggle. Tags are shown on each result (clicking one toggles that filter) and in the note view. After create, update and delete the tag bar and suggestions are reloaded and `selected` is reduced to tags that still exist. An empty result with a selected tag shows "Brak wyników". Tag text is only inserted with `textContent`/`value`, never `innerHTML`.
#### 2. `tests/test_notes.py`
**Intent**: Keep the page contract tested.
**Contract**: page smoke test asserts the tag bar, the tag inputs (`#tags`, `#etags`) and the absence of `innerHTML`.
#### 3. `README.md`
**Intent**: Mention tags.
**Contract**: the status line says notes can be tagged and filtered by tag.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
#### Manual Verification
- Create a note with tags `SQL, Soft Skills`; it shows `soft skills` and `sql`; typing the keyword finds it
- Clicking tags in the bar narrows the list; two tags show only notes with both; clicking again widens; text and tag filters combine
- Editing the tags updates the bar and counts; removing the last note with a tag removes it from the bar and from a selected filter
- Suggestion buttons append existing tags without duplicating
- Tags with `<b>` or `<script>` show as text
- Tags survive `docker compose down` / `up --build`

## Testing Strategy
API tests (Phase 1) cover normalisation, filtering, cleanup and the old-schema case; Phase 2 adds a page smoke test and manual browser checks.

## Performance Considerations
The tag filter is a subquery over `note_tags` (indexed on `tag_id`, primary key on `(note_id, tag_id)`); with MVP data volumes this is negligible. Tags for a result page are loaded in one extra query (no N+1). The 5000-note timing test must stay green.

## Migration Notes
No migration: new tables are created on connect; existing notes simply have no tags.

## Open Risks & Assumptions
- `bazy`, `database` and `db` remain separate tags; suggestions are the only mitigation (PRD keeps tag management out of scope).
- Tags are listed alphabetically, not in entry order.
- A `PUT` without `tags` clears them; the UI always sends the field.
- Text search does not match tag words until S-06.

## References
- PRD US-01, FR-006, FR-008; roadmap S-05
- `src/compass/db.py`, `src/compass/notes.py`, `src/compass/api.py`, `src/compass/page.py`

## Progress

### Phase 1: Tags in data and API
#### Automated
- [x] 1.1 `uv run pytest` passes
- [x] 1.2 ruff check and format check pass
- [x] 1.3 mypy strict passes
#### Manual
- [x] 1.4 curl: create tagged notes, list tags, filter by one and two tags

### Phase 2: Tags in the UI
#### Automated
- [x] 2.1 `uv run pytest` passes
- [x] 2.2 ruff, format check and mypy pass
- [x] 2.3 `docker build -t compass:dev .` passes
#### Manual
- [x] 2.4 A note created with tags shows them and is found by keyword
- [x] 2.5 The tag bar narrows the list (two tags = AND) and combines with text
- [x] 2.6 Editing tags updates the bar; unused tags disappear, also from a selected filter
- [x] 2.7 Suggestion buttons append existing tags without duplicates
- [x] 2.8 HTML in tags is shown as text
- [x] 2.9 Tags survive `down`/`up --build`
