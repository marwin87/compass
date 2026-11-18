# S-05 e2e-tests Implementation Plan

## Overview
Automated end-to-end tests that drive the real app in a real browser. They use Playwright for Python through `pytest-playwright`, live in `tests/e2e/`, and are run **locally only** with one command (`uv run pytest -m e2e`). CI is not changed: a plain `uv run pytest` skips them. There is one phase for the infrastructure and one phase per flow, ten flows in all, each phase ending with a repeatable passing set.

## Current State Analysis
- `tests/` holds backend tests (one file per area) and `tests/ui/` holds UI tests: markup and i18n guards through `TestClient`, plus the pure JavaScript of the reader and the editor run in Node. `tests/conftest.py` sets `COMPASS_PASSWORD=test-password` and `COMPASS_SECRET_KEY` before the app is imported and gives every test its own database (`db_file`, autouse) and an `authed` client.
- The behaviour of the page script (forms, filters, popups, reading mode, settings, managers) is verified only by throwaway headless-Chromium scripts that are not in the repository; nothing repeatable checks the real screens.
- CI (`.github/workflows/ci.yml`): `guard`, `lint` (ruff, mypy `src tests`), `test` (`pytest --cov`, coverage gate 80%, Node for the parser tests) and `docker` (build and smoke test). Dependabot is gone.
- The UI is built from DOM calls with plenty of `aria-label`, `title`, roles and visible text, so role and label locators are available almost everywhere. Native `<dialog>` is used for popups, the toast is `#toast`, the app resets cleanly through `DELETE /api/data` and `PUT /api/settings`.
- `CLAUDE.md` fixes the rules for E2E work: `getByRole` / `getByLabel` / `getByText` first, `getByTestId` only when ambiguous, never `page.waitForTimeout()`, each test independent with unique ids (timestamp suffix) and its own cleanup, DOM snapshot as the default and vision only for visual-only risks; the `/10x-e2e` skill is the workflow (risk, seed test, generate, review, verify).

## Desired End State
- `uv sync` installs `pytest-playwright`; `uv run playwright install chromium` downloads the browser once.
- `uv run pytest -m e2e` starts the app on a free port with a temporary database, runs about fifty tests in headless Chromium and prints a short result; `--headed --slowmo 300` runs them visibly; a failing test leaves a trace and a screenshot in `test-results/`.
- `uv run pytest` (and CI) collects the e2e tests, deselects them by the `e2e` marker and needs no browser.
- Each of the ten flows has its own test module and the suite passes three runs in a row.

### Key Discoveries
- Python-side plumbing is cheap because the app is one process: `python -m uvicorn compass.main:app` with `COMPASS_DB_PATH`, `COMPASS_PASSWORD` and `COMPASS_SECRET_KEY` in the environment is the whole server; `/health` tells when it is up.
- Reset between tests does not need a restart: `DELETE /api/data` empties notes, tags and categories and `PUT /api/settings` restores the defaults; cookies disappear with the fresh browser context Playwright gives each test.
- A plain `pytest` must stay browser-free. The package goes into the default dev group (it is only a Python wheel), so `uv sync --locked`, ruff and mypy in CI keep working, and the `e2e` marker plus `addopts = -m "not e2e"` keep the tests out of the default run and the coverage figure.
- Real-browser behaviour the earlier throwaway scripts could not show: `requestAnimationFrame`, smooth scrolling, clipboard, downloads and the native dialogs all work, but animations must be reduced (`reduced_motion="reduce"` in the browser context) and the clipboard needs a granted permission.

## What We're NOT Doing
A CI job for these tests, Firefox or WebKit runs, pixel or visual regression, load or performance tests, testing the Docker image (its smoke test does that), parallel workers (one server and one database per session is enough locally), adding `data-testid` attributes unless a locator is truly ambiguous.

## Implementation Approach
- Infrastructure first, with one real passing test (the "seed test" of `/10x-e2e`), so every later phase only adds a module.
- A `tests/e2e/` package: `conftest.py` (server, base URL, login and reset fixtures, browser context options), `pages.py` (tiny helpers for repeated actions such as "add a note"), and one module per flow named `test_<flow>.py`.
- Every test builds its own data through the UI or the API with unique titles (`name-<timestamp>`), asserts with web-first `expect(...)` (auto-waiting, no sleeps) and never depends on another test's data.
- After each phase: run the new module three times, then the whole e2e suite once, and the plain `uv run pytest` plus `ruff` and `mypy` to prove nothing else changed.

## Phase 0: Infrastructure and a seed test

### Changes Required
#### 1. `pyproject.toml`, `uv.lock`
**Intent**: Add the dependency and keep the default test run browser-free.
**Contract**: `pytest-playwright` in the `dev` group; `[tool.pytest.ini_options]` gets `markers = ["e2e: browser tests, run with -m e2e"]` and `addopts = "-m 'not e2e'"`; `test-results/` goes into `.gitignore`.
#### 2. `tests/e2e/__init__.py`, `tests/e2e/conftest.py`
**Intent**: A real server and a clean state for every test.
**Contract**: session fixture `server` starts `python -m uvicorn compass.main:app` on a free port with a temporary database and the test password (the `COMPASS_*` variables, set explicitly so a developer's `.env` never leaks), waits for `/health` (30 s limit, readable error with the server log on failure) and stops it at the end; fixture `base_url` overrides the plugin's; autouse fixture `clean` runs `DELETE /api/data` and `PUT /api/settings` with the defaults before each test (through `httpx` with a logged-in session); `browser_context_args` sets `reduced_motion="reduce"`, a fixed viewport (1280x800), locale `pl-PL` and the clipboard permissions; `page` fixture override that logs in unless the test asks for `anon_page`; a mark registration so `@pytest.mark.e2e` is applied to the whole package.
#### 3. `tests/e2e/pages.py`
**Intent**: Do repeated steps once.
**Contract**: small functions `unique(prefix)`, `add_note(page, title, body="", tags=(), category=None)` (opens the form, fills it, saves, waits for the card), `open_settings(page, section)`; no assertions hidden inside.
#### 4. `tests/e2e/test_smoke.py` (the seed test)
**Intent**: Prove the stack end to end.
**Contract**: "a note added through the form is found by search": log in (fixture), add a note with a unique title, search for a part of the title, expect exactly that card and its detail panel.
#### 5. `README.md`, `AGENTS.md`
**Intent**: One documented way to run them.
**Contract**: a short "End-to-end tests" section: `uv run playwright install chromium` (once), `uv run pytest -m e2e`, `--headed --slowmo 300`, `--tracing retain-on-failure` is on by default; "local only, not in CI".

### Success Criteria
#### Automated Verification
- `uv run pytest -m e2e` passes (seed test), also three times in a row
- `uv run pytest` still passes with the same count as before and without a browser installed
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
#### Manual Verification
- `uv run pytest -m e2e --headed --slowmo 300` shows the browser adding and finding the note
- A deliberate failure (temporarily) leaves a trace and a screenshot in `test-results/`

## Phase 1: Login and access (`test_login.py`)
**Tests**: a wrong password stays on the login page with the message; the right password opens the notes page; anonymous visits to `/` and `/settings` land on the login page; the session survives a reload; logout returns to the login page and `/` is closed again; the language buttons on the login page switch the texts and the choice survives a reload.
**Files**: `tests/e2e/test_login.py`.

### Success Criteria
#### Automated Verification
- `uv run pytest -m e2e tests/e2e/test_login.py` passes three times; whole suite passes; `uv run pytest`, ruff and mypy unchanged
#### Manual Verification
- Headed run of the module looks like a real login

## Phase 2: Create and search (`test_notes_create_search.py`)
**Tests**: create a note with a title, body, two tags and a category through the form (card appears, selected, toast, counts in the side panel update); an empty title is refused with the message; search finds by body word, by tag, by prefix; a typo (`indkes`) and a missing Polish letter (`zlozonosc`) still find the note; a query with no match shows the "no results" text; `Esc` clears the search; the `/` and `Ctrl+K` shortcuts focus the search box; `N` opens a new note.
**Files**: `tests/e2e/test_notes_create_search.py`.

### Success Criteria
#### Automated Verification
- The module passes three times; the whole e2e suite once; `uv run pytest`, ruff and mypy unchanged
#### Manual Verification
- Headed run shows the typing, the debounce and the highlighted matches

## Phase 3: Edit and delete (`test_notes_edit_delete.py`)
**Tests**: edit changes the title, body and tags after the "overwrite" confirmation and keeps the creation date; cancelling the confirmation keeps the old text; "Back" from the confirmation returns to the form with the typed text; delete asks first, "Back" keeps the note, confirming removes it from the list, the counts and the search; deleting the last note shows the empty state; both actions are reachable by keyboard (focus order, Enter).
**Files**: `tests/e2e/test_notes_edit_delete.py`.

### Success Criteria
#### Automated Verification
- The module passes three times; the whole e2e suite once; `uv run pytest`, ruff and mypy unchanged
#### Manual Verification
- The two-step confirmations read clearly in a headed run

## Phase 4: Markdown editor (`test_editor.py`)
**Tests**: the bold button wraps the selection and the second click unwraps it; `Ctrl+B` and `Ctrl+I` work in the textarea; undo (`Ctrl+Z`) reverts a toolbar edit; heading, bullet and numbered lists, quote, code (inline and fenced), link and table insert what they should; the callout menu opens, offers six kinds, `Esc` closes only the menu, choosing one inserts the block; the Preview tab renders headings, lists, a callout, a code block and a table, shows raw HTML as text and goes back to Write with the text untouched; the saved note renders the same in the note panel; the toolbar is hidden in the preview.
**Files**: `tests/e2e/test_editor.py`.

### Success Criteria
#### Automated Verification
- The module passes three times; the whole e2e suite once; `uv run pytest`, ruff and mypy unchanged
#### Manual Verification
- Typing, selecting and clicking the toolbar feels right in a headed run (focus stays in the textarea)

## Phase 5: Reading mode (`test_reading_mode.py`)
**Tests**: the book icon enters reading mode (sidebar, list, search hidden; reading bar visible; the icon is lit and pressed); clicking it again and `Esc` and the "Esc Exit" button each leave it; the font size buttons change the text size and the width button cycles; the contents appear for a note with three or more `##`/`###` headings, clicking an entry scrolls to the section and highlights it, a short note has no contents; the arrow keys do not switch notes while reading; editing leaves reading mode.
**Files**: `tests/e2e/test_reading_mode.py`.

### Success Criteria
#### Automated Verification
- The module passes three times; the whole e2e suite once; `uv run pytest`, ruff and mypy unchanged
#### Manual Verification
- Headed run: the layout change and the sticky contents look right on a long note

## Phase 6: Filters and sorting (`test_filters_sort.py`)
**Tests**: clicking a tag filters and clicking again clears; two tags combine as AND; a category filter and a tag filter combine; a filter plus a search combine; "Wszystkie" clears tag and category filters but keeps the text, "Czyść" clears everything; counts next to the tags and categories are right; the five sort orders reorder the list (A-Z with Polish letters, Z-A, oldest, newest, default relevance while searching); `↑`/`↓` move through the list and keep the card in view.
**Files**: `tests/e2e/test_filters_sort.py`.

### Success Criteria
#### Automated Verification
- The module passes three times; the whole e2e suite once; `uv run pytest`, ruff and mypy unchanged
#### Manual Verification
- Headed run of a combined filter looks right

## Phase 7: Settings persistence (`test_settings.py`)
**Tests**: the theme switch changes the colours at once and survives a reload and a fresh context (server-side store); the language switch changes the interface and survives a reload; the reading size and width set in Settings are used by reading mode; the default sort set in Settings is selected on the notes page; a failing save (route blocked in the test) reverts the control and shows the error toast; the sidebar button opens Settings, the back link returns; the navigation highlights the clicked section, including the last ones.
**Files**: `tests/e2e/test_settings.py`.

### Success Criteria
#### Automated Verification
- The module passes three times; the whole e2e suite once; `uv run pytest`, ruff and mypy unchanged
#### Manual Verification
- Headed run: theme and language changes feel immediate

## Phase 8: Data tools (`test_data_tools.py`)
**Tests**: export downloads `compass-export-<date>.json` and its content has the notes, tags and categories; import of a file (`setInputFiles`) asks first in the popup, cancelling or `Esc` changes nothing, confirming replaces all data and shows the result toast; importing the demo file fills the categories; a broken file shows the translated error and keeps the data; "Clear all data" asks first, cancel keeps everything, confirm empties notes, tags and categories and the counts in About.
**Files**: `tests/e2e/test_data_tools.py`.

### Success Criteria
#### Automated Verification
- The module passes three times; the whole e2e suite once; `uv run pytest`, ruff and mypy unchanged
#### Manual Verification
- Headed run of import and clear shows the popups and the safe default focus

## Phase 9: Tag and category management (`test_manage_lists.py`)
**Tests**: tags: search (case and accents), sorting, rename with the cleaned name, a merge asks first and shows both counts, "Back" returns to the field, confirming merges and the notes keep one tag, delete asks and removes the tag from the notes, the notes page reflects the changes (filter list, search by the new name); categories: add, duplicate refused, reserved name refused, rename, delete refused when not empty (with the count), delete when empty, search; both lists scroll inside their card with 60 entries and show the cap hint beyond 300.
**Files**: `tests/e2e/test_manage_lists.py`.

### Success Criteria
#### Automated Verification
- The module passes three times; the whole e2e suite once; `uv run pytest`, ruff and mypy unchanged
#### Manual Verification
- Headed run of a merge reads clearly

## Phase 10: Mobile layout (`test_mobile.py`)
**Tests**: with a 390x800 viewport: the menu button opens the drawer, the scrim and `Esc` close it; selecting a note opens the detail view and the back arrow returns to the list; reading mode works and the page never scrolls horizontally; the note form and the editor toolbar wrap without overflow; the Settings page shows the chip navigation and no horizontal overflow; long lists stay inside their scrolling cards.
**Files**: `tests/e2e/test_mobile.py` (with `browser.new_context(viewport=...)` through a fixture).

### Success Criteria
#### Automated Verification
- The module passes three times; the whole e2e suite passes three times in a row; `uv run pytest` (without the browser), ruff, mypy and `docker build` unchanged
#### Manual Verification
- Headed mobile run looks like a phone

---

## Progress

### Phase 0: Infrastructure and a seed test
#### Automated
- [x] 0.1 `uv run pytest -m e2e` passes the seed test, three times in a row
- [x] 0.2 `uv run pytest` is unchanged and needs no browser; ruff, format and mypy pass
- [x] 0.3 `docker build -t compass:dev .` passes
#### Manual
- [ ] 0.4 A headed run shows the browser adding and finding a note
- [ ] 0.5 A failing test leaves a trace and a screenshot in `test-results/`

### Phase 1: Login and access
#### Automated
- [x] 1.1 The login module passes three times; the whole suite and the plain `pytest` are unchanged
#### Manual
- [ ] 1.2 Headed run looks like a real login

### Phase 2: Create and search
#### Automated
- [x] 2.1 The create and search module passes three times; the whole suite and the plain `pytest` are unchanged
#### Manual
- [ ] 2.2 Headed run shows typing, debounce and highlights

### Phase 3: Edit and delete
#### Automated
- [x] 3.1 The edit and delete module passes three times; the whole suite and the plain `pytest` are unchanged
#### Manual
- [ ] 3.2 The confirmations read clearly in a headed run

### Phase 4: Markdown editor
#### Automated
- [x] 4.1 The editor module passes three times; the whole suite and the plain `pytest` are unchanged
#### Manual
- [ ] 4.2 Typing, selecting and the toolbar feel right in a headed run

### Phase 5: Reading mode
#### Automated
- [x] 5.1 The reading mode module passes three times; the whole suite and the plain `pytest` are unchanged
#### Manual
- [ ] 5.2 Layout change and sticky contents look right on a long note

### Phase 6: Filters and sorting
#### Automated
- [x] 6.1 The filters and sorting module passes three times; the whole suite and the plain `pytest` are unchanged
#### Manual
- [ ] 6.2 A combined filter looks right in a headed run

### Phase 7: Settings persistence
#### Automated
- [x] 7.1 The settings module passes three times; the whole suite and the plain `pytest` are unchanged
#### Manual
- [ ] 7.2 Theme and language changes feel immediate

### Phase 8: Data tools
#### Automated
- [x] 8.1 The data tools module passes three times; the whole suite and the plain `pytest` are unchanged
#### Manual
- [ ] 8.2 Import and clear show the popups with the safe default focus

### Phase 9: Tag and category management
#### Automated
- [x] 9.1 The management module passes three times; the whole suite and the plain `pytest` are unchanged
#### Manual
- [ ] 9.2 A merge reads clearly in a headed run

### Phase 10: Mobile layout
#### Automated
- [x] 10.1 The mobile module passes three times; the whole suite passes three times in a row; plain `pytest`, ruff, mypy and `docker build` unchanged
#### Manual
- [ ] 10.2 A headed mobile run looks like a phone
