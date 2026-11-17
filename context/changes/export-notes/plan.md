# S-01 export-notes Implementation Plan

## Overview
A logged-in user can download all their notes, with tags and creation dates, as one JSON file. It is a usable backup on its own (FR-009, export half; PRD "no data loss") and it fixes the file format that import (S-02) will read back.

## Current State Analysis
- `src/compass/notes.py`: `list_notes` is capped at 50 (`LIMIT`) and ranks by relevance, so it cannot serve as an export. `_with_tags` builds `IN (?, ?, ...)` clauses, which would hit SQLite's parameter limit for very large databases. `Note` is `{id, title, body, created_at, tags}`.
- `src/compass/api.py`: routers `router` (`/api/notes`) and `tags_router` (`/api/tags`), registered in `create_app()`; the guard in `auth.py` returns 401 JSON for anonymous `/api/*`.
- `src/compass/page.py`: panel layout page; UI text comes from `src/compass/i18n.py` (`[[key]]` markers filled on the server, `tr("key")` in JS); `tests/test_i18n.py` checks key parity and that every key is used.
- No `updated_at` column: the only date a note has is `created_at` (ISO 8601 UTC, seconds).

## Desired End State
`GET /api/export` (logged in) returns a downloadable file `compass-export-<YYYY-MM-DD>.json` containing every note, newest first, with tags and creation dates:
```json
{"format": "compass-export", "version": 1, "exported_at": "<ISO UTC>", "count": N,
 "notes": [{"id": 12, "title": "...", "body": "...", "tags": ["a", "b"], "created_at": "..."}, ...]}
```
UTF-8 with real Polish letters (not `\uXXXX` escapes), indented for reading. An empty database yields a valid file with `"notes": []` and `"count": 0`. The page has an "Eksportuj notatki" / "Export notes" button in the side panel that downloads it. The search box and tag filter do not affect the export.

### Key Discoveries
- Export needs its own query, not `list_notes`: no cap, no ranking, and one `JOIN` with `group_concat` over `note_tags`/`tags` instead of `IN (...)` lookups.
- `count` in the file lets the importer (S-02) detect a truncated or hand-edited file; `format` and `version` let it refuse files it does not understand.
- A single `SELECT` is one consistent snapshot, so a note edited during the export cannot appear half-updated.
- Anonymous access is already refused by the `/api/*` guard, so the endpoint needs no auth code of its own.

## What We're NOT Doing
Import (S-02), a second format (Markdown or CSV), exporting only the filtered view, an `updated_at` field (the data model has none), compression or streaming (a few thousand notes is a few MB), scheduled or automatic backups, encrypting the file, a client-side fetch-and-blob download with its own 401 handling (a plain link is enough; an expired session shows the 401 message instead of a file).

## Implementation Approach
- `notes.export_all()` runs one query: `notes LEFT JOIN note_tags LEFT JOIN tags`, `GROUP BY n.id`, `ORDER BY n.id DESC`, tags collected with `group_concat(t.name, char(10))` and split and sorted in Python (tags cannot contain newlines because normalisation collapses whitespace).
- `api.py` gets an `export_router` at `/api/export` returning a `Response` with the JSON text, `media_type="application/json"`, `Content-Disposition: attachment; filename="compass-export-<date>.json"` and `Cache-Control: no-store`; `exported_at` and the file name date come from the same `datetime.now(UTC)`.
- The UI button is a plain `<a href="/api/export" download>` styled as a button; text via i18n keys.

## Phase 1: Export endpoint

### Changes Required
#### 1. `src/compass/notes.py`
**Intent**: Read every note with its tags in one pass.
**Contract**: `export_all() -> list[Note]`, newest first (`id DESC`), tags alphabetical, no limit. Uses one `SELECT ... LEFT JOIN ... GROUP BY n.id`; no parameter lists.
#### 2. `src/compass/api.py` and `src/compass/main.py`
**Intent**: Serve the file.
**Contract**: `GET /api/export` → 200, body is the JSON document above (`format` `"compass-export"`, `version` `1`, `exported_at`, `count`, `notes`), `json.dumps(..., ensure_ascii=False, indent=2)` encoded as UTF-8; headers `Content-Disposition: attachment; filename="compass-export-YYYY-MM-DD.json"` and `Cache-Control: no-store`. Query parameters such as `q` and `tag` are ignored. The router is included in `create_app()`.
#### 3. `tests/test_export.py` (new)
**Intent**: Pin the file format and its guarantees.
**Contract**: document shape and constants (`format`, `version`, ISO `exported_at`, `count == len(notes)`); more than 50 notes are all exported (for example 120); order is newest first; tags are alphabetical and present; each note's fields equal what `GET /api/notes/{id}` returns; empty database gives `notes == []` and `count == 0`; Polish letters, newlines, quotes, commas, emoji and `</script>` in title, body and tags survive a `json.loads` round trip unchanged and the file contains the letters themselves rather than `\u` escapes; `q` and `tag` query parameters do not change the result; headers (`attachment` filename pattern with today's date, `no-store`); anonymous request is 401 (the guard also protects `/api/export`); exporting does not modify the database; a timing test with 5000 notes finishes well under a second (assert under 1 s).

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- `uv run mypy src tests`
#### Manual Verification
- With `curl` and a session cookie: `curl -OJ localhost:8011/api/export` saves a file with the expected name; it opens as valid JSON containing all notes

---

## Phase 2: Export button

### Changes Required
#### 1. `src/compass/i18n.py`
**Intent**: UI text in both languages.
**Contract**: new keys `export` ("Eksportuj notatki" / "Export notes") and `export_title` ("Pobierz wszystkie notatki jako plik JSON" / "Download all notes as a JSON file"), present in `pl` and `en` (parity and usage tests keep passing).
#### 2. `src/compass/page.py`
**Intent**: A visible, accessible way to download the backup.
**Contract**: in the side panel, above the log-out button, `<a class="btn wide" href="/api/export" download title="[[export_title]]">[[export]]</a>` (centered text, same look as the other buttons); no JS needed.
#### 3. `tests/` and `README.md`
**Intent**: Keep the page contract tested and document the file.
**Contract**: the page smoke test asserts the link to `/api/export` in both languages; README gets a short "Export" section describing the file (format, version, fields, newest first, UTF-8) and that import comes later.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
#### Manual Verification
- In the browser the button downloads `compass-export-<today>.json`; the file holds all notes (also when the list is filtered), newest first, with correct tags, dates and Polish letters
- The button label and tooltip follow the PL/EN switch
- With no notes the download works and the file contains an empty list

## Testing Strategy
API tests (Phase 1) pin the format and its edge cases; Phase 2 adds a page smoke test. The round trip (export then import into an empty app) is tested in S-02.

## Performance Considerations
One query and one `json.dumps` of the whole list in memory: fine for the MVP's volume (5000 notes is a few MB). If it ever grows large, switch to a streaming response.

## Open Risks & Assumptions
- Newest-first order was chosen to match the list in the app: S-02 must import in ascending `id` order (oldest first) to keep the notes' relative order.
- `id` values are exported for reference only; a fresh instance will assign its own ids, so S-02 must not rely on them being preserved.
- The file holds all notes in plain text: protect it like the database itself.
- An expired session makes the link show the 401 message instead of a file.

## References
- PRD FR-009, Success Criteria §Secondary and §Guardrails; roadmap M-02 S-01
- `src/compass/notes.py`, `src/compass/api.py`, `src/compass/page.py`, `src/compass/i18n.py`

## Progress

### Phase 1: Export endpoint
#### Automated
- [x] 1.1 `uv run pytest` passes
- [x] 1.2 ruff check and format check pass
- [x] 1.3 mypy strict passes
#### Manual
- [x] 1.4 curl downloads a valid JSON file with all notes

### Phase 2: Export button
#### Automated
- [x] 2.1 `uv run pytest` passes
- [x] 2.2 ruff, format check and mypy pass
- [x] 2.3 `docker build -t compass:dev .` passes
#### Manual
- [x] 2.4 Button downloads the file; content correct also with a filtered list
- [x] 2.5 Label and tooltip follow the PL/EN switch
- [x] 2.6 Export works with no notes (empty list)
