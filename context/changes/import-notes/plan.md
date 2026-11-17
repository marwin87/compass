# S-02 import-notes Implementation Plan

## Overview
A logged-in user can load notes from a file made by the Export button back into Compass without losing a title, a body, a tag or a creation date. Exporting and then importing the same file into an empty Compass must reproduce the notes, their tags, their order and their search results: that is the quality bar of milestone M-02.

## Current State Analysis
- Export (S-01): `GET /api/export` returns `{"format": "compass-export", "version": 1, "exported_at", "count", "notes": [{id, title, body, tags, created_at}]}`, newest first, UTF-8 (`src/compass/api.py`, `notes.export_all`).
- `src/compass/notes.py`: `create_note` stamps `created_at` with "now", so it cannot be reused for import. Building blocks that can be reused: `normalize_tags` (limits: at most 10 tags, each 1..30 characters, no commas), `_save_tags`, `db.index_note` (writes the folded search index row), `connect()` (foreign keys on, index created and migrated).
- `NoteIn` limits: title 1..200 characters after stripping, body up to 20000.
- The guard answers 401 JSON for anonymous `/api/*`; the page has a side panel with an Export link and UI text in `src/compass/i18n.py` (Polish and English, `[[key]]` markers and `tr("key")`), checked by `tests/test_i18n.py` (key parity, every key used).
- There is no import code or control.

## Desired End State
`POST /api/import` takes the export document as its JSON body, validates all of it first, and then writes it in one transaction. Valid files give `200 {"imported": n, "skipped": m, "total": n+m}`; invalid files give `422 {"detail": {"code": ..., ...}}` and change nothing. A note counts as already present when title, body and creation date are all identical to an existing note (tags and `id` do not matter); such notes are skipped and the existing note is left untouched. Notes are inserted oldest first, keep their `created_at` and get new ids. The side panel has an "Importuj notatki" / "Import notes" button that opens a file picker, uploads the chosen file, and shows a translated summary or error; the list and the tag bar refresh.

### Key Discoveries
- Importing oldest first (export is newest first) makes the new ids ascend with `created_at`, so the "newest first" list looks the same as before the export.
- The identity rule (title, body, creation date) makes an import idempotent across instances too, because it ignores ids: importing A's file into B and then again into B skips everything the second time.
- Duplicates must be counted as a multiset: if the file holds two identical notes and the app one, exactly one is imported; into an empty app both are imported (no data loss).
- Validation has to finish before the first write, so "all or nothing" needs no rollback logic for bad files; the single `BEGIN IMMEDIATE` transaction only covers unexpected database errors.
- Error codes (not English sentences) travel from the API to the page, which maps them to translated messages.

## What We're NOT Doing
Other sources or formats (Markdown, plain JSON lists, other tools), overwriting or merging existing notes (a skipped duplicate keeps its own tags), importing the valid notes of a file that contains an invalid one, a preview or confirmation step, undoing an import, preserving the original ids, progress reporting, chunked or streamed upload, importing into a filtered view.

## Implementation Approach
- New module `src/compass/transfer.py` (no database access): `parse_export(document) -> list[ParsedNote]` validates the document and raises `BadExport(code, **info)`; `ParsedNote` has `title`, `body`, `tags` (normalised), `created_at` (string kept as in the file) and the parsed datetime used for ordering.
- `notes.import_notes(items) -> tuple[int, int]` does the database work: one `BEGIN IMMEDIATE` transaction, existing `(title, body, created_at)` loaded into a `Counter`, items ordered oldest first, duplicates consume the counter, the rest are inserted with `_save_tags` and `index_note`.
- `api.py` gets `POST /api/import` (reads the body, caps its size, parses JSON, calls the two functions, maps `BadExport` to 422).

## Phase 1: Import API

### Changes Required
#### 1. `src/compass/transfer.py` (new)
**Intent**: Validate an export document completely before anything is written.
**Contract**: `parse_export(document: object) -> list[ParsedNote]`, raising `BadExport` with `code` and details: `not_an_export` (not an object, or `format` is not `compass-export`), `unsupported_version` (`version` is not 1; detail `version`), `invalid_file` (`notes` missing or not a list), `count_mismatch` (`count` differs from the list length; details `expected`, `actual`), `invalid_note` (details `index`, 1-based position in the file, and `field`: `title`, `body`, `tags` or `created_at`; the note is not an object, the title is empty or longer than 200 characters after stripping, the body is not a string or exceeds 20000, tags are not a list of strings or break `normalize_tags`, `created_at` is not an ISO 8601 date-time). The `id` field is optional and ignored. The first problem found is reported.
#### 2. `src/compass/notes.py`
**Intent**: Write the parsed notes atomically, skipping what is already there.
**Contract**: `import_notes(items: Sequence[ParsedNote]) -> tuple[int, int]` returns `(imported, skipped)`. Order: oldest first by parsed `created_at`, ties keeping the file's reverse order (the file is newest first). Existing notes are matched on `(title, body, created_at)` as a multiset. Inserted notes keep `created_at` exactly as written in the file, get new ids, and are indexed with their tags.
#### 3. `src/compass/api.py` and `src/compass/main.py`
**Intent**: Expose the import.
**Contract**: `POST /api/import`, JSON body = the export document. 200 `{"imported", "skipped", "total"}`; 422 `{"detail": {"code", ...}}` for `BadExport` and `{"detail": {"code": "not_json"}}` when the body is not valid JSON; 413 `{"detail": {"code": "file_too_large", "limit_mb": 50}}` when the body exceeds 50 MB (a module constant). Router included in `create_app()`.
#### 4. `tests/test_import.py` (new)
**Intent**: Prove the round trip and every rule.
**Contract**: the full round trip: build notes (Polish letters, newlines, tags, several creation times), export from database A, import into an empty database B (switch `COMPASS_DB_PATH`), then the notes, tags, tag counts, newest-first order and the results of several searches (a word, a diacritic-free spelling, a typo, a tag filter) match A, and B's own export equals A's apart from ids and `exported_at`; ids in B ascend with creation time; importing the same file again imports 0 and skips all; importing A's file into A skips everything; identical notes in a file (same title, body, date) both arrive in an empty app and both are skipped on re-import; one identical note already present imports exactly the other copy; a note edited after export is not a duplicate and arrives as an extra note (documents the chosen rule); existing tags of a skipped duplicate stay unchanged; invalid inputs (not JSON, top-level array, wrong `format`, `version` 2, missing or non-list `notes`, `count` mismatch, and for each of the four fields an invalid note) give 422 with the right `code`, `index` and `field`, and a valid note before an invalid one is not imported; a hand-edited note with unnormalised tags (`" SQL "`, duplicates) is imported with normalised tags; 5000 notes import in a few seconds (assert under 5 s); anonymous request is 401; an oversized body is 413 (limit lowered by monkeypatch).

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- `uv run mypy src tests`
#### Manual Verification
- With `curl`: export from one instance, import into a second empty instance (another `COMPASS_DB_PATH`), and the notes, tags and dates match; importing the same file again reports everything as skipped

---

## Phase 2: Import button

### Changes Required
#### 1. `src/compass/i18n.py`
**Intent**: UI text in both languages.
**Contract**: new keys, present in `pl` and `en`: `import`, `import_title`, `import_done` (`{n}` imported, `{m}` skipped), `import_err_not_json`, `import_err_not_an_export`, `import_err_unsupported_version` (`{version}`), `import_err_invalid_file`, `import_err_count_mismatch` (`{expected}`, `{actual}`), `import_err_invalid_note` (`{index}`, `{field}`; says nothing was imported), `import_err_file_too_large` (`{mb}`), `import_err_failed`, and field names `field_title`, `field_body`, `field_tags`, `field_created_at`.
#### 2. `src/compass/page.py`
**Intent**: Pick a file, upload it, show the outcome.
**Contract**: in the side panel above the Export link, `<button type="button" class="btn wide" id="import" title="[[import_title]]">[[import]]</button>` and a hidden `<input type="file" id="importfile" accept=".json,application/json">`; a status line `<div id="importmsg" role="status">` under the buttons. Clicking the button opens the picker; on change, read the file as text, `POST /api/import` with `content-type: application/json`, then on 200 show `import_done` (success style), reload the tag bar and the list; on 422/413 map `detail.code` (and `field`) to the translated message (error style, stays until the next import); any other failure shows `import_err_failed`. Reset the input value so the same file can be chosen again. A 401 redirects to `/login` like every other call. Text is set with `textContent` only.
#### 3. `tests/` and `README.md`
**Intent**: Keep the page contract tested and document the rules.
**Contract**: the page smoke test asserts the import button, the file input and the status line in both languages; README's Export section gains an "Import" paragraph: only files made by the Export button, a note whose title, body and creation date match an existing one is skipped, a file with any invalid note is rejected as a whole, creation dates are kept and ids are new.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
- A headless-browser run against the real page with a stubbed API: successful import (message, refreshed list), duplicate-only import, each error code, and both languages
#### Manual Verification
- Export, delete a few notes, import the same file: the deleted notes return with their tags and dates, the rest is reported as skipped
- Importing the same file twice never duplicates anything
- Choosing a wrong file (a text file, JSON that is not an export, an export with a broken note) shows a clear translated message and changes nothing
- Messages follow the PL/EN switch

## Testing Strategy
API tests (Phase 1) cover validation, atomicity, identity rules and the round trip; Phase 2 adds a page smoke test and a real-browser run against a stubbed API, plus manual checks.

## Performance Considerations
One transaction, existing identities loaded once into a `Counter`, one insert plus one index write per note: 5000 notes should import in about a second or two. The whole file is held in memory (capped at 50 MB).

## Migration Notes
None: no schema change, and the export format is unchanged (version 1).

## Open Risks & Assumptions
- A note edited after the export is no longer "the same" (its body differs), so an old file brings the old version back as an additional note instead of overwriting; this is the chosen, safe behaviour (no overwrite).
- A skipped duplicate keeps its own tags; tags in the file are not merged in.
- Ids are not preserved; creation dates have one-second precision, so two different notes created in the same second with identical title and body are treated as identical (both are kept on an empty import thanks to the multiset rule).
- An import cannot be undone as a whole; unwanted notes are deleted one by one.
- Everything is validated against the limits of today's app (title 200, body 20000, 10 tags of 30 characters); a future export from a more permissive version would be refused by `version`.

## References
- PRD FR-009, Success Criteria §Secondary and §Guardrails; roadmap M-02 S-02; `context/changes/export-notes/plan.md`
- `src/compass/notes.py`, `src/compass/db.py`, `src/compass/api.py`, `src/compass/page.py`, `src/compass/i18n.py`

## Progress

### Phase 1: Import API
#### Automated
- [x] 1.1 `uv run pytest` passes
- [x] 1.2 ruff check and format check pass
- [x] 1.3 mypy strict passes
#### Manual
- [x] 1.4 curl: export from one instance, import into an empty second one: notes, tags and dates match; a second import skips everything

### Phase 2: Import button
#### Automated
- [x] 2.1 `uv run pytest` passes
- [x] 2.2 ruff, format check and mypy pass
- [x] 2.3 `docker build -t compass:dev .` passes
- [x] 2.4 Headless-browser run: success, duplicates, every error code, both languages
#### Manual
- [x] 2.5 Deleted notes come back from an export with tags and dates; the rest is reported as skipped
- [x] 2.6 Importing the same file twice never duplicates anything
- [x] 2.7 Wrong files show a clear translated message and change nothing
- [x] 2.8 Messages follow the PL/EN switch
