# S-04 settings-page Implementation Plan

## Overview
A separate **Settings** page where configuration lives, starting with what already exists (appearance, data, keyboard shortcuts, about) and ready to host server-side configuration later (API, LLM, ...). Preferences move from the browser (`localStorage`) to a server-side `settings` table, and import, export and category management move out of the sidebar into the page. EN/PL and the theme switch stay in the sidebar footer as quick toggles (they are also in Settings).

## Current State Analysis
- The UI is one server-rendered page, `src/compass/page.py`, with one `<script>` holding the generic helpers (`h`, `tr`, `icon`, `toast`, `api`, ...); `src/compass/reader.py` holds the Markdown reader and its styles; the login page reuses only `COMMON_CSS`.
- Preferences are scattered: theme, reading size/width and the list sort live in `localStorage`; the language is a cookie (`lang`, also needed by the login page and the server render).
- The category manager (`renderManage`, `categoryCall`, `categoryError`, dialog `#catdialog`) and the import flow (`importFile`, popup `#importdialog`, Import/Export buttons) live in `page.py`; the sidebar footer has EN, PL, theme, Import, Export, Logout.
- `main.py` serves `/` and `/health`; the guard in `auth.py` redirects anonymous non-API requests to `/login` and answers 401 JSON for `/api/*`. `db.py` creates tables in `SCHEMA`; `notes.replace_all` already replaces all data in one transaction.
- `STYLE_GUIDE.md` fixes the frontend rules: DOM calls only, no external requests, every string in both languages, no dead controls, exactly one `</script>`.

## Desired End State
- `GET /settings` (behind the guard): sections Appearance, Data, Shortcuts, About with a left nav that highlights the current section (chip row on mobile) and a back link to the notes.
- A `settings` table and `/api/settings` (GET all effective values, PUT a validated partial update); keys `theme`, `reader_size`, `reader_width`, `sort`. The notes page gets its theme (as `<html data-theme>`) and values embedded by the server, so there is no flash and no extra request; every change is saved at once with a toast.
- Appearance: theme, language (cookie + reload), reading text size and width, default sort. Shortcuts: a table. About: version, counts, database size and path (`GET /api/about`). Data: inline category manager, Export, Import (confirmation popup), Clear all data (`DELETE /api/data`, confirmation popup).
- Sidebar: Settings button in the footer, "Zarządzaj" links to `/settings#data`; Import/Export buttons and the category dialog are gone.

### Key Discoveries
- Language must stay a cookie: the login page and the first server render need it before any setting can be read.
- Reusing `notes.replace_all([], [])` makes "Clear all data" one transaction with the same guarantees as import.
- The helpers shared by two pages have to leave `page.py` first, otherwise the Settings page would copy them: they move verbatim to `core.py` (the same marker mechanism the reader already uses).
- The settings registry gives later features (API, LLM) a one-line way in: a key with a default and a validator, plus an i18n key and a test. A future secret flag would make a key write-only; not built now.

## What We're NOT Doing
API/LLM sections or secret handling (added with their first real feature), changing the password from the UI, tag management (rename/merge), migrating old `localStorage` values (they reset once to defaults), moving the language to the server, a Save button (every control applies at once).

## Implementation Approach
- Server first (store and API with tests), then the shared JS core and the notes page reading its settings from the server, then the new page, then the Data section and the sidebar cleanup. Each phase leaves the app working.
- Settings values are JSON text in a `key`/`value` table; validation per key in `src/compass/settings.py`; one JS helper `saveSetting(key, value)` (PUT, toast, revert on failure).
- Verification uses pytest for the server and the headless-Chromium method from `STYLE_GUIDE.md` for the UI.

## Phase 1: Settings store, API, about, clear data

### Changes Required
#### 1. `src/compass/settings.py` (new), `src/compass/db.py`
**Intent**: Persist validated settings.
**Contract**: `SCHEMA` adds `settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)`. `SPEC` maps each key to a default and a validator: `theme` `dark|light` (default `dark`), `reader_size` int 15-22 (17), `reader_width` int 0-2 (1), `sort` `""` or one of `notes.SORTS` (`""`). `all()` returns every key with its effective value; `update(patch)` validates the whole patch first and writes it in one transaction (an unknown key or invalid value raises `SettingError(key)` and changes nothing); an empty patch is a no-op.
#### 2. `src/compass/api.py`, `src/compass/main.py`
**Intent**: Expose the store, the about info and clear data.
**Contract**: `GET /api/settings`, `PUT /api/settings` (422 `{"code": "invalid_setting", "key": ...}`); `GET /api/about` returns `{version, notes, categories, tags, db_size_bytes, db_path}` (version from `importlib.metadata`, fallback `"dev"`); `DELETE /api/data` returns 204 after `notes.replace_all([], [])`. All behind the guard.
#### 3. `tests/test_settings.py` (new)
**Intent**: Pin the behaviour.
**Contract**: defaults; partial update persists across reconnect; per-key validation incl. bounds; unknown key; empty patch; atomic update (one bad key changes nothing); about fields and version fallback; clear data empties everything, keeps the default category and a working app; 401 when logged out.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
#### Manual Verification
- With curl: GET/PUT `/api/settings`, `/api/about`, `DELETE /api/data` on a throwaway database

## Phase 2: Shared JS core; the notes page reads server settings

### Changes Required
#### 1. `src/compass/core.py` (new), `src/compass/page.py`, `src/compass/reader.py`
**Intent**: One copy of the helpers for both pages; the notes page stops using `localStorage` for preferences.
**Contract**: `CORE_JS` holds, verbatim: the I18N constants, `tr`, `$`, `h`, ICONS/`svg`/`icon`/`fillIcons`, `toast`, `api`, `json`, `saveSetting`, the category error table and `categoryError`; embedded into `INDEX_HTML` through a marker (still one `</script>`). Theme toggle, reading size/width and the sort select call `saveSetting`; their initial values come from `SETTINGS`.
#### 2. `src/compass/main.py`, `src/compass/page.py`
**Intent**: No flash, no extra fetch.
**Contract**: `render_index(lang, settings=None)` embeds `const SETTINGS = ...` (`</` escaped) and sets `data-theme` on `<html>`; `main.index` passes `settings.all()`; without the argument the defaults are used.
#### 3. `tests/`
**Intent**: Keep the guards meaningful.
**Contract**: the i18n usage tests also scan `CORE_JS`; new tests for `data-theme`, the embedded blob and the defaults.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
- Headless Chromium, both languages and themes: preferences persist after reload without a flash, and every earlier flow (filter, forms, reader, reading mode, sort, skeleton, import popup) still passes
#### Manual Verification
- Change theme, reading size and sort, reload and open a second browser: the values follow the server

## Phase 3: Settings page: Appearance, Shortcuts, About

### Changes Required
#### 1. `src/compass/settings_page.py` (new), `src/compass/main.py`
**Intent**: The page and its route.
**Contract**: `SETTINGS_CSS`, a template and `SETTINGS_JS` (DOM calls, tokens from `COMMON_CSS`, `CORE_JS`), `render_settings(lang, settings)`; `GET /settings`. Appearance: theme (segmented), language (EN/PL), reading size (A-/A+ with the value) and width (narrow/medium/wide), default sort (same labels as the list). Shortcuts: a table (`/`, Ctrl/Cmd K, `N`, arrows, Esc, reading mode). About: from `/api/about`, with skeleton and an error state with retry. Every control saves at once (toast; on failure the control reverts).
#### 2. `src/compass/page.py`, `src/compass/i18n.py`
**Intent**: Reach the page and translate it.
**Contract**: a Settings button (gear) in the sidebar footer; new keys in both languages.
#### 3. `tests/test_settings_page.py` (new), `tests/test_i18n.py`
**Intent**: Pin the page.
**Contract**: `/settings` needs login, renders in both languages with all sections and makes no external request; the usage tests also scan the settings page.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
- Headless Chromium: each control sends its PUT and updates the page, a failed save reverts and toasts, nav scroll-spy, 390 px width without horizontal overflow, About success and error states
#### Manual Verification
- Appearance changes apply at once and survive a reload; the language switch works
- The page looks right in dark and light, at desktop and phone width

## Phase 4: Data section and sidebar cleanup

### Changes Required
#### 1. `src/compass/settings_page.py`
**Intent**: Move, not copy, the data tools.
**Contract**: the category manager as an inline list (add, rename, delete with two-step confirm, `not_empty` count, default row fixed, the same translated errors); Export (download link + toast); Import (file, confirmation popup, replace, result in a toast); Clear all data (red button, popup, `DELETE /api/data`, toast).
#### 2. `src/compass/page.py`, `src/compass/i18n.py`
**Intent**: A lighter sidebar.
**Contract**: remove the category dialog, the import flow and the Import/Export buttons; "Zarządzaj" becomes a link to `/settings#data`; the notes page reloads categories on load, and quick add in the note forms stays.
#### 3. `STYLE_GUIDE.md`, `README.md`, `demo/README.md`, tests
**Intent**: Keep the docs and guards current.
**Contract**: a Settings section in the style guide (new settings go through the registry, an i18n key and a test); README mentions Settings; browser harnesses for import and categories point at `/settings`.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
- Headless Chromium, both languages: category add/rename/delete/not-empty, import cancel/confirm/error, clear data cancel/confirm, export toast
#### Manual Verification
- A full pass on a copy of real data: import the demo file, manage categories, export, clear all data, re-import
- The sidebar has no import/export/manage dialog left; the Settings button and the "Zarządzaj" link work

---

## Progress

### Phase 1: Settings store, API, about, clear data
#### Automated
- [x] 1.1 `uv run pytest` passes (settings, about, clear data)
- [x] 1.2 ruff, format check and mypy pass
- [x] 1.3 `docker build -t compass:dev .` passes
#### Manual
- [x] 1.4 curl: GET/PUT `/api/settings`, `/api/about`, `DELETE /api/data` behave as specified

### Phase 2: Shared JS core; the notes page reads server settings
#### Automated
- [x] 2.1 `uv run pytest` passes
- [x] 2.2 ruff, format check and mypy pass
- [x] 2.3 `docker build -t compass:dev .` passes
- [x] 2.4 Headless-browser run: settings persistence and all earlier flows, both languages and themes
#### Manual
- [x] 2.5 Theme, reading size/width and sort persist across reloads and a second browser, no flash

### Phase 3: Settings page: Appearance, Shortcuts, About
#### Automated
- [x] 3.1 `uv run pytest` passes
- [x] 3.2 ruff, format check and mypy pass
- [x] 3.3 `docker build -t compass:dev .` passes
- [x] 3.4 Headless-browser run for the Settings page (controls, revert on failure, scroll-spy, mobile, about error state)
#### Manual
- [x] 3.5 Appearance changes apply at once and survive reload; language switch works
- [x] 3.6 Settings looks right in dark and light, desktop and phone width

### Phase 4: Data section and sidebar cleanup
#### Automated
- [x] 4.1 `uv run pytest` passes
- [x] 4.2 ruff, format check and mypy pass
- [x] 4.3 `docker build -t compass:dev .` passes
- [x] 4.4 Headless-browser run for the moved Data flows, both languages
#### Manual
- [x] 4.5 Categories, import, export and clear all data work from Settings
- [x] 4.6 The sidebar has no import/export/manage dialog left; Settings button and "Zarządzaj" link work
