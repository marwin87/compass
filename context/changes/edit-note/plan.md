# S-03 edit-note Implementation Plan

## Overview
A logged-in user can edit an existing note (title and body) and the change is saved, visible in the list and found by search under the new text.

## Current State Analysis
- `src/compass/notes.py`: `create_note`, `get_note`, `list_notes`; `notes` table plus FTS5 external-content index `notes_fts(title, body, content='notes', content_rowid='id')`. Insert writes to both in one transaction. No update path.
- `src/compass/api.py`: `POST /api/notes`, `GET /api/notes`, `GET /api/notes/{id}`; `NoteIn` validates title (stripped, 1..200) and body (<=20000).
- `src/compass/page.py`: one HTML page with inline JS, note view (`#view`), all note text inserted via `textContent`.
- The guard returns 401 JSON for anonymous `/api/*`.
- List order is `id DESC` (creation order); there is no `updated_at`.

## Desired End State
`PUT /api/notes/{id}` replaces title and body. The note view has an "Edytuj" button that turns it into a form with the current values, "Zapisz" (with a second confirming step) and "Anuluj". After saving, the list and the view show the new text; search finds the note by the new words and no longer by removed ones. The note keeps its place in the list.

### Key Discoveries
- FTS5 external-content tables are not updated by a plain `UPDATE` on `notes`. The index must be told to drop the old entry with the special `'delete'` command (passing the OLD title/body) and then get the new one, in the same transaction; otherwise stale words still match.
- `NoteIn` already carries the validation rules, so the update body can reuse it.
- Overwriting has no history by design (PRD counter-argument kept as written).

## What We're NOT Doing
History/undo, `updated_at` and re-ordering by edit time, editing tags (S-05), delete (S-04), concurrent-edit conflict detection, native `window.confirm()` dialogs, partial updates (PATCH).

## Implementation Approach
- `update_note(id, title, body)` reads the old row, writes the new values to `notes`, and updates `notes_fts` (`'delete'` with old values, then insert new) inside one transaction; returns the updated `Note` or `None` when the id does not exist.
- `PUT /api/notes/{id}` reuses `NoteIn`; 404 for unknown id.
- Confirmation is an inline two-step button (no native dialog): the first "Zapisz" click turns the control into "Na pewno nadpisać? Tak, nadpisz / Wróć"; only "Tak, nadpisz" sends the request.

## Phase 1: Update API and index

### Changes Required
#### 1. `src/compass/notes.py`
**Intent**: Add the update operation that keeps the FTS index in sync.
**Contract**: `update_note(note_id: int, title: str, body: str) -> Note | None`; single transaction; for an existing row: `UPDATE notes`, then `INSERT INTO notes_fts(notes_fts, rowid, title, body) VALUES('delete', id, old_title, old_body)` followed by a normal insert of the new values. `created_at` is unchanged. Returns `None` if the id is missing (nothing written).
#### 2. `src/compass/api.py`
**Intent**: Expose the update.
**Contract**: `PUT /api/notes/{note_id}` with body `NoteIn` returns the updated `Note` (200), 404 `Note not found`, 422 on validation errors.
#### 3. `tests/test_notes.py`
**Intent**: Prove the index follows the edit.
**Contract**: edit then GET shows new values and the same `created_at`; old word no longer finds the note, new word does (title-only edit and body-only edit); position in the list is unchanged; an edit does not duplicate results; unknown id 404; invalid title 422 and nothing changed; anonymous PUT 401.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- `uv run mypy src tests`
#### Manual Verification
- With `curl` and a session cookie: PUT a note, then search by the old and new word

---

## Phase 2: Edit in the UI

### Changes Required
#### 1. `src/compass/page.py`
**Intent**: Let the user edit from the note view.
**Contract**: the note view gets an "Edytuj" button. Edit mode swaps the text for a form (title input, body textarea, prefilled). "Zapisz" first shows the inline confirmation ("Na pewno nadpisać?" with "Tak, nadpisz" and "Wróć"); only the confirming button calls `PUT /api/notes/{id}`. "Anuluj" restores the read view without any request. After a successful save: refresh the list, show the updated note in read mode. On 401 go to `/login`; on a validation error show the message and stay in edit mode. All note text still goes in via `textContent`/`value`, never `innerHTML`.
#### 2. `tests/test_notes.py`
**Intent**: Keep the page contract tested.
**Contract**: page smoke test asserts the edit controls exist in the served HTML and `innerHTML` is still absent.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
#### Manual Verification
- Edit a note title and body; the list and the view show the new text; search finds it by a new word and not by a removed word
- "Anuluj" and "Wróć" change nothing
- A validation error (empty title) shows a message and keeps the edit form
- The edited note keeps its place in the list; the edit survives `docker compose down` / `up --build`

## Testing Strategy
API tests (Phase 1) cover the index synchronisation; Phase 2 adds a page smoke test and manual browser checks.

## Open Risks & Assumptions
- Overwrite has no history; the two-step confirmation is the only protection.
- No conflict detection: the last save wins if the same note is edited in two tabs.
- Existing databases need no migration (no schema change).

## References
- PRD FR-004; roadmap S-03
- `src/compass/notes.py`, `src/compass/api.py`, `src/compass/page.py`

## Progress

### Phase 1: Update API and index
#### Automated
- [x] 1.1 `uv run pytest` passes
- [x] 1.2 ruff check and format check pass
- [x] 1.3 mypy strict passes
#### Manual
- [x] 1.4 curl: PUT a note and search by old and new word

### Phase 2: Edit in the UI
#### Automated
- [x] 2.1 `uv run pytest` passes
- [x] 2.2 ruff, format check and mypy pass
- [x] 2.3 `docker build -t compass:dev .` passes
#### Manual
- [x] 2.4 Edited title and body appear in list and view; search follows the new text
- [x] 2.5 "Anuluj" and "Wróć" change nothing
- [x] 2.6 Empty title shows a message and keeps the edit form
- [x] 2.7 Edited note keeps its list position and survives `down`/`up --build`
