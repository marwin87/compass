# S-04 delete-note Implementation Plan

## Overview
A logged-in user can permanently delete a note; it disappears from the list, from search and from the database. A confirmation step guards against a stray click.

## Current State Analysis
- `src/compass/notes.py`: `create_note`, `get_note`, `list_notes`, `update_note`. `notes` table plus FTS5 external-content index `notes_fts(title, body, content='notes', content_rowid='id')`. `update_note` already shows the pattern for keeping the index in step (`'delete'` command with the OLD values inside one `BEGIN IMMEDIATE` transaction).
- `src/compass/api.py`: `POST`, `GET` (list/search), `GET /{id}`, `PUT /{id}`; 404 `Note not found` for unknown ids; the guard returns 401 for anonymous `/api/*`.
- `src/compass/page.py`: note view (`#read` with "Edytuj", `#editform` with a two-step inline confirmation), all note text via `textContent`; `[hidden]{display:none !important}` already in the CSS.
- `id` is `INTEGER PRIMARY KEY` without `AUTOINCREMENT`, so SQLite may reuse the id of the most recently deleted note; nothing references note ids outside the API.

## Desired End State
`DELETE /api/notes/{id}` removes the note and its index entry and returns 204 (404 when the id does not exist). The note view has a "Usuń" button with a two-step confirmation ("Na pewno usunąć? Tak, usuń / Wróć"). After deleting, the view closes, the list is refreshed, and a short "Notatka usunięta" message is shown above the list. If the note was already gone, the UI behaves the same as after a successful delete.

### Key Discoveries
- Removing the row from `notes` alone leaves the words in the external-content index; it must be told to forget them via `INSERT INTO notes_fts(notes_fts, rowid, title, body) VALUES('delete', id, old_title, old_body)` using the values as indexed.
- The two-step confirmation pattern from S-03 (`askConfirm`) can be mirrored for delete.

## What We're NOT Doing
Soft delete/trash/undo, bulk delete, deleting from the list without opening the note, native `window.confirm()` dialogs, idempotent 204 for missing notes, renumbering ids.

## Implementation Approach
- `delete_note(id) -> bool` runs in one `BEGIN IMMEDIATE` transaction: read the old row, `'delete'` it from `notes_fts`, delete it from `notes`; returns `False` when the id is missing.
- `DELETE /api/notes/{id}` returns 204 or 404.
- The UI adds a delete control to the read view with an inline two-step confirmation, and treats 404 like success.

## Phase 1: Delete API and index

### Changes Required
#### 1. `src/compass/notes.py`
**Intent**: Add the delete operation that keeps the FTS index in sync.
**Contract**: `delete_note(note_id: int) -> bool`; single transaction; existing row: `'delete'` command into `notes_fts` with the old title/body, then `DELETE FROM notes WHERE id = ?`; returns `True`. Missing id: nothing written, returns `False`.
#### 2. `src/compass/api.py`
**Intent**: Expose the delete.
**Contract**: `DELETE /api/notes/{note_id}` → 204 with no body; 404 `Note not found` when `delete_note` returns `False`.
#### 3. `tests/test_notes.py`
**Intent**: Prove the note is gone everywhere.
**Contract**: delete then `GET /{id}` is 404; the list no longer contains it; a search by a word of the deleted note (title and body) returns nothing; other notes are untouched and still searchable; deleting twice gives 204 then 404; deleting an unknown id is 404; anonymous `DELETE` is 401; a note created after a delete still works (no index corruption), including when it reuses the freed id.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- `uv run mypy src tests`
#### Manual Verification
- With `curl` and a session cookie: DELETE a note, then GET it and search by its words

---

## Phase 2: Delete in the UI

### Changes Required
#### 1. `src/compass/page.py`
**Intent**: Let the user delete from the note view with a safeguard.
**Contract**: the read view gets a "Usuń" button next to "Edytuj". Clicking it swaps the buttons for "Na pewno usunąć? Tak, usuń / Wróć" (no native dialog); only "Tak, usuń" calls `DELETE /api/notes/{id}`. 204 or 404: hide the view, reload the list, show "Notatka usunięta" in a status element above the list (cleared on the next search/save). 401 goes to `/login`; any other error shows a message and keeps the view. The delete controls are not available while editing. No `innerHTML`.
#### 2. `tests/test_notes.py`
**Intent**: Keep the page contract tested.
**Contract**: page smoke test asserts the delete controls exist in the served HTML and `innerHTML` is still absent.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
#### Manual Verification
- Open a note, "Usuń", confirm: it disappears from the list and from search, and "Notatka usunięta" shows
- "Wróć" leaves the note untouched
- Delete a note in one tab, then delete it from a second tab that still shows it: the second tab ends in the same state with no error
- Deleted notes stay gone after `docker compose down` / `up --build`

## Testing Strategy
API tests (Phase 1) cover the index synchronisation and error cases; Phase 2 adds a page smoke test and manual browser checks.

## Open Risks & Assumptions
- Deletion is irreversible; the two-step confirmation is the only safeguard.
- SQLite may reuse the id of the last deleted note; harmless today (no references to ids).
- Existing databases need no migration.

## References
- PRD FR-005; roadmap S-04
- `src/compass/notes.py` (`update_note` for the FTS pattern), `src/compass/api.py`, `src/compass/page.py`

## Progress

### Phase 1: Delete API and index
#### Automated
- [x] 1.1 `uv run pytest` passes
- [x] 1.2 ruff check and format check pass
- [x] 1.3 mypy strict passes
#### Manual
- [x] 1.4 curl: DELETE a note, then GET and search by its words

### Phase 2: Delete in the UI
#### Automated
- [x] 2.1 `uv run pytest` passes
- [x] 2.2 ruff, format check and mypy pass
- [x] 2.3 `docker build -t compass:dev .` passes
#### Manual
- [x] 2.4 Delete with confirmation removes the note from list and search and shows the message
- [x] 2.5 "Wróć" leaves the note untouched
- [x] 2.6 Deleting an already deleted note from a second tab ends in the same state
- [x] 2.7 Deleted notes stay gone after `down`/`up --build`
