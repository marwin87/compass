# S-02 first-note-search Implementation Plan

## Overview
The north star: a logged-in user saves a note (title + body), views it, and finds it again by typing a few letters of a keyword. Plain keyword match only; ranking, typo and Polish-diacritics tolerance belong to S-06, tags to S-05.

## Current State Analysis
- `src/compass/db.py`: `connect()` opens `COMPASS_DB_PATH` and creates only a `meta` table.
- `src/compass/main.py`: `create_app()` builds the app; `/` is an HTML stub with a logout button; `/health` public.
- `src/compass/auth.py`: `guard` middleware redirects every non-public, unauthenticated request to `/login` (303). `PUBLIC_PATHS = {"/login", "/health"}`.
- Tests: `tests/test_app.py` + `tests/conftest.py` (env vars set before import), `TestClient(app, follow_redirects=False)`.
- FTS5 is available in local SQLite (3.50) and in the Docker image (`python:3.12-slim-bookworm`, SQLite 3.40).
- `../../../prototypes/compass-prototyp.html` is a UI reference only (not served).

## Desired End State
After login, `/` shows a search box, a list of notes (newest first), an add-note form and a note view. Typing filters the list live (prefix match, case-insensitive, any word matches). Notes survive `docker compose down` / `up --build` and are wiped by `down -v`.

### Key Discoveries
- Search terms must be sanitised before `MATCH`: raw user input breaks FTS5 syntax (quotes, `-`, `*`, `AND`).
- The guard returns a redirect; JSON clients need a 401 instead (`/api/*`).
- Existing tests hit `/` and log in; they keep working, new tests extend them.

## What We're NOT Doing
Tags (S-05), edit (S-03), delete (S-04), relevance ranking, title-above-body, typo tolerance and Polish diacritics (S-06), keywords/domain fields from the prototype, pagination beyond a 50-result cap, Next.js, FTS update/delete triggers (added by S-03/S-04).

## Implementation Approach
- Schema in `db.connect()` via `CREATE ... IF NOT EXISTS`: `notes(id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)` and FTS5 external-content table `notes_fts(title, body, content='notes', content_rowid='id')`.
- A small `notes.py` module owns create/get/list/search; creating a note inserts into `notes` and `notes_fts` in one transaction.
- Query building: split input into word tokens (`\w+`, Unicode), quote each and add `*` (prefix), join with `OR`; no tokens means list all. Order by `id DESC`, `LIMIT 50`.
- JSON API under `/api/notes` with Pydantic models; guard returns 401 JSON for `/api/*`, redirect for everything else.
- UI: single HTML page with inline JS, debounce about 100 ms, `fetch` to the API.

## Phase 1: Notes data and API

### Changes Required
#### 1. `src/compass/db.py`
**Intent**: Create the notes table and the FTS5 index next to `meta`.
**Contract**: `connect()` idempotently creates `notes` and `notes_fts` (external content, columns `title`, `body`).
#### 2. `src/compass/notes.py` (new)
**Intent**: Note storage and search, free of HTTP concerns.
**Contract**: `create_note(title, body) -> Note`, `get_note(id) -> Note | None`, `list_notes(q: str = "") -> list[Note]` (cap 50, newest first). `Note` is a typed dataclass/Pydantic model with `id`, `title`, `body`, `created_at`. Search token builder is a pure function covered by tests (empty, punctuation-only, quotes, `*`, `-`, `AND`).
#### 3. `src/compass/api.py` (new) and `main.py`
**Intent**: Expose the notes as JSON and register the router.
**Contract**: `POST /api/notes` (title 1..200 chars, body up to 20000) → 201 + note; `GET /api/notes/{id}` → note or 404; `GET /api/notes?q=` → list. Router included in `create_app()`.
#### 4. `src/compass/auth.py`
**Intent**: Unauthenticated `/api/*` gets 401 JSON instead of a redirect.
**Contract**: in `guard`, paths starting with `/api/` return `JSONResponse({"detail": "Not authenticated"}, 401)`; all other behaviour unchanged.
#### 5. Tests
**Intent**: Cover create/read/search and the access rules.
**Contract**: create → get; prefix (`ind` finds "Indeks"); case-insensitive; OR across words; empty query lists all, newest first; no match returns empty; special characters in the query do not error; title validation (empty, too long) → 422; anonymous `/api/notes` → 401; 404 for unknown id; a timing test searching about 5000 notes finishes well under a generous bound (for example 200 ms).

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- `uv run mypy src tests`
#### Manual Verification
- With `curl` and a session cookie: create a note, fetch it, search by a prefix
- Anonymous `curl /api/notes` returns 401

---

## Phase 2: Notes UI and persistence

### Changes Required
#### 1. `src/compass/main.py` (index page)
**Intent**: Replace the stub with the notes page.
**Contract**: `/` serves one HTML page (inline CSS and JS): search input, results list (title plus short body excerpt), add-note form (title, body), note view (click a result), logout button kept. JS debounces input (about 100 ms), calls `GET /api/notes?q=`, renders results with `textContent` (never `innerHTML` with note data, to avoid XSS), and refreshes the list after a save. Empty query shows all notes.
#### 2. Page markup kept in one place
**Intent**: Avoid a template engine for one page.
**Contract**: the HTML lives in a module-level constant or a static file served by the app; no new dependency.
#### 3. `README.md`
**Intent**: Note what the app does now.
**Contract**: status line mentions notes and search.

### Success Criteria
#### Automated Verification
- `uv run pytest` (a test that `/` after login contains the search input)
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
#### Manual Verification
- Add a note, find it by typing the first letters of a word from the title and from the body
- Results update while typing without a visible delay; clicking a result shows the full note
- A note with `<script>` or `<b>` in it is displayed as text
- `docker compose down && up --build`: notes still there; `down -v && up --build`: empty

## Testing Strategy
API tests (Phase 1) carry the behaviour; Phase 2 adds a smoke test for the page and manual browser checks.

## Open Risks & Assumptions
- OR across words was chosen; without ranking, multi-word queries can be noisy until S-06.
- `LIMIT 50` hides older matches until S-06 adds ranking and pagination if needed.
- Prefix matching does not find a fragment inside a word (e.g. `deks`) and does not fold `ł` to `l`; both are S-06.
- Timing test threshold is deliberately generous to avoid flaky CI.

## References
- PRD US-01, FR-002, FR-003, FR-007; NFR on response time
- `src/compass/db.py`, `src/compass/auth.py`, `src/compass/main.py`, `../../../prototypes/compass-prototyp.html`

## Progress

### Phase 1: Notes data and API
#### Automated
- [x] 1.1 `uv run pytest` passes
- [x] 1.2 ruff check and format check pass
- [x] 1.3 mypy strict passes
#### Manual
- [x] 1.4 curl: create, fetch and prefix-search a note with a session cookie
- [x] 1.5 Anonymous `/api/notes` returns 401

### Phase 2: Notes UI and persistence
#### Automated
- [x] 2.1 `uv run pytest` passes (including the page smoke test)
- [x] 2.2 ruff, format check and mypy pass
- [x] 2.3 `docker build -t compass:dev .` passes
#### Manual
- [x] 2.4 A saved note is found by the first letters of a title word and a body word
- [x] 2.5 Results update while typing; clicking a result shows the note
- [x] 2.6 HTML in a note is shown as text
- [x] 2.7 Notes survive `down`/`up --build` and are wiped by `down -v`
