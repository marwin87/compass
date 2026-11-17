# S-03 note-categories Implementation Plan

## Overview
Every note belongs to exactly one category, and the user can narrow the list to one category with a single click. Categories come from a managed list (create, rename, delete) kept in a window opened from the side panel, and a new category can also be added on the spot from the add and edit note forms. A built-in default category, "Bez kategorii" / "Uncategorized", holds notes that were never categorised. Category is different from a tag: one per note and mandatory, whereas tags are many and optional.

## Current State Analysis
- `src/compass/db.py`: `SCHEMA` creates `meta`, `notes(id, title, body, created_at)`, `tags`, `note_tags`; the folded search index is created and migrated by `_ensure_index`. `connect()` turns foreign keys on and runs the schema on every connection.
- `src/compass/notes.py`: `Note` is `{id, title, body, created_at, tags}`; `create_note`, `update_note` (full replacement), `list_notes(q, tags)` (ranked text search with a tag AND-filter, newest first without a query), `export_all`, `import_notes`.
- `src/compass/api.py`: routers for notes, tags, export and import; `NoteIn` validates title, body and tags; the guard answers 401 JSON for anonymous `/api/*`.
- `src/compass/page.py` and `src/compass/i18n.py`: panel layout (tag bar with counts, results, note card), forms built from DOM calls, UI text in Polish and English with parity tests.
- Export (S-01) writes `format: compass-export`, `version: 1`; import (S-02) accepts exactly version 1 and identifies duplicates by title, body and creation date. `demo/compass-demo.json` is a version 1 file kept valid by `tests/test_demo.py`.
- Existing databases and old export files have notes with no category.

## Desired End State
- A `categories` table and a mandatory `notes.category_id`. Category 1 is the built-in default; existing notes and old import files end up in it. A note created or updated without a category goes to the default.
- `GET /api/categories` returns every category with its note count; `POST`, `PUT` and `DELETE /api/categories` manage the list.
- `GET /api/notes?category_id=N` returns only the notes of that category and combines with the text query and the tag filter by AND.
- The side panel has a "Kategorie" / "Categories" section: "Wszystkie" / "All" and each category with its count, one selected at a time (click the selected one again to clear). A "Zarządzaj" / "Manage" button opens the management window. Note forms have a category field with a quick "new category" option (a new category can be created, and then selected, without leaving the form); the note card and the result list show the category.
- Export carries each note's category name; import creates the categories a file mentions and puts notes without one in the default. The export format is not versioned: the `version` field is removed from export and import (there is one format), and files that still contain it import fine because unknown fields are ignored.

### Key Discoveries
- SQLite refuses `ALTER TABLE ... ADD COLUMN x NOT NULL DEFAULT 1 REFERENCES categories(id)` while foreign keys are on (and `connect()` turns them on). The column is therefore added without `REFERENCES`; the code and a test keep `category_id` valid, and a category can only be deleted when no note uses it, so no orphan can appear.
- The default category needs a language-independent identity: it is row id 1 flagged `is_default`, its stored name is empty, and the page shows the translated label. Exports write `null` for it, so a file never contains a language-specific name.
- Category names are unique ignoring case and diacritics (a folded key, as the search does), so "Łódź" and "lodz" cannot coexist. The names "Bez kategorii" and "Uncategorized" are reserved (they would look like the default).
- The search index and ranking are untouched: the category is a filter, not searchable text.
- Importing a file that names a category Compass does not have creates it, otherwise those notes would lose their category; names that match the default's labels map to the default.
- Dropping `version` also drops the `unsupported_version` error and its translations; `format` (`compass-export`) stays as the marker that a file is an export, and `count` stays as the truncation check.

## What We're NOT Doing
Versioning the export format (there is exactly one format; `version` is removed), searching category names as text, nested categories, several categories per note, colours or icons, merging categories (a rename onto an existing name is refused), deleting a category together with its notes, moving notes in bulk, ordering the list by hand, keyboard shortcuts for categories, multi-select filtering, renaming or deleting the default category.

## Implementation Approach
- New module `src/compass/categories.py` owns the rules: name normalisation, the folded key, reserved names, list with counts, create, rename, delete, and `ensure(conn, name)` used by import. `notes.py` stores and filters by `category_id`.
- Errors are codes in `{"detail": {"code": ...}}` (`name_invalid`, `name_reserved`, `name_taken`, `default_category`, `not_empty` with the note count, `not_found`, `invalid_category`); the page translates them.
- Phases follow the layers: data and API, note-level UI and the filter, the management window, then export, import and demo.

## Phase 1: Data and API

### Changes Required
#### 1. `src/compass/db.py`
**Intent**: Create the category table, add the column and migrate old databases.
**Contract**: `SCHEMA` gains `categories(id INTEGER PRIMARY KEY, name TEXT NOT NULL, key TEXT NOT NULL UNIQUE, is_default INTEGER NOT NULL DEFAULT 0)`. After the schema script `connect()` ensures the default row (`id 1`, empty name, empty key, `is_default 1`) and that `notes` has `category_id INTEGER NOT NULL DEFAULT 1` (added with `ALTER TABLE` when `PRAGMA table_info(notes)` lacks it, tolerating a concurrent connection having done it first) plus an index on `notes(category_id)`. Idempotent; existing notes get category 1.
#### 2. `src/compass/categories.py` (new)
**Intent**: Category rules in one place.
**Contract**: `Category` model (`id`, `name`, `default`, `count`); `normalize(name)` trims and collapses whitespace, 1..40 characters, else `name_invalid`; the key is the folded name; the keys `""`, `bez kategorii` and `uncategorized` are reserved (`name_reserved`); `list_categories()` (default last, others by folded name, each with its note count); `create(name)` (a duplicate name raises `name_taken` carrying the existing category's `id`); `rename(id, name)` (refuses the default with `default_category`, duplicates with `name_taken`, unknown ids with `not_found`); `delete(id)` (refuses the default, a non-empty category with `not_empty` and its `count`, unknown ids with `not_found`); `exists(id)`; `default_id() -> 1`; `ensure(conn, name | None)` returns the id of the category with that name, creating it if needed, mapping `None` and the default's labels to the default.
#### 3. `src/compass/notes.py`, `src/compass/api.py`, `src/compass/main.py`
**Intent**: Carry the category through notes and expose the list.
**Contract**: `Note` gains `category_id: int`. `NoteIn` gains `category_id: int | None = None`; `None` means the default (full replacement on `PUT`, like tags); an id that does not exist gives 422 `invalid_category`. `create_note`, `update_note`, `get_note`, `list_notes` and `export_all` read and write it. `list_notes(q, tags, category_id=None)` adds `n.category_id = ?` to both the no-query path and the ranked path (as `rowid IN (SELECT id FROM notes WHERE category_id = ?)` next to the existing tag filter). `GET /api/notes` takes `category_id`. A `categories_router` at `/api/categories`: `GET` (list), `POST` `{name}` → 201, `PUT /{id}` `{name}`, `DELETE /{id}` → 204; errors as codes (422 for name problems, 409 for `name_taken` with the existing category's `id`, `default_category` and `not_empty`, 404 for `not_found`).
#### 4. `tests/test_categories.py` (new) and updates
**Intent**: Pin every rule and the migration.
**Contract**: the default exists on a fresh database; create, rename, delete and list with counts and ordering; creating a name that exists (also differing in case or diacritics) is refused with `name_taken` and the existing id; name rules (empty, 41 characters, whitespace collapsed, case and diacritics-insensitive uniqueness, reserved names, case change of the same category allowed on rename); rename or delete of the default refused; delete of a non-empty category refused with its count and allowed once emptied; a note created without a category lands in the default, with a valid one lands there, with an unknown id gets 422; update changes it and omitting it resets to the default; the category filter alone and combined with text and with tags (AND), with a ranked query and with none; counts follow note creation, move and deletion; a database created before this change (notes without the column, an old search index) opens, gains the column and the default row, keeps every note in category 1 and keeps searching; `PUT`/`POST` of notes still work with old clients that send no category; anonymous requests are 401.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- `uv run mypy src tests`
#### Manual Verification
- With `curl`: create two categories, put notes in them, list with counts, filter notes by `category_id`, try renaming onto an existing name and deleting a non-empty category (both refused with a code)

---

## Phase 2: Categories in notes and the filter

### Changes Required
#### 1. `src/compass/i18n.py`
**Intent**: Text for the new UI in both languages.
**Contract**: keys for the section heading, "all", the default category's label (`category_default`), the form label (`label_category`), the manage button, the badge/title strings, the quick-add strings (`category_new`, `category_new_ph`, `category_add`) and the translated category error messages (`category_err_name_invalid`, `category_err_name_reserved`, `category_err_name_taken`, `category_err_default_category`, `category_err_not_empty`, `category_err_not_found`, `category_err_failed`) which the management window in Phase 3 reuses; parity and usage tests keep passing.
#### 2. `src/compass/page.py`
**Intent**: Choose a category per note and filter by it.
**Contract**: state gets `category` (id or null). `loadCategories()` fetches `/api/categories`; the side panel gets a "Kategorie" section above the tags: an "All (N)" entry and each category with its count (the default last and shown with its translated label), the selected one highlighted, a second click clears; `load()` sends `category_id`. The add and edit forms get a `<select>` of the categories with a "+ New category" button next to it; a new note preselects the filtered category when there is one, otherwise the default; an edited note preselects its own; the value is sent as `category_id`. **Quick add**: the button reveals a small inline field (name, Add, Cancel); Add (or Enter, which must not submit the note form) calls `POST /api/categories`; on success the category joins the select and is selected, the panel's categories reload and focus returns to the select; if the name already exists (`name_taken` carries its id) that existing category is simply selected instead of showing an error; other problems (`name_invalid`, `name_reserved`, failures) show the translated message under the field; Cancel closes the field. A category created this way stays in the list even if the note form is then cancelled (it can be deleted in the management window). Result cards show a small category badge for non-default categories; the note card always shows the category. After create, edit and delete the category counts reload; creating a note clears the category filter like it clears tags and text. Names are set with `textContent` only; a filter on a category that disappears is dropped.
#### 3. `tests/`
**Intent**: Keep the page contract tested.
**Contract**: smoke test for the section and the select in both languages; the Chromium run against a stubbed API (as before) covers selecting, clearing and combining the filter, the form select, the badge, the counts after edit and delete, quick add in both the add and the edit form (a new name is created and selected, an existing name is selected without a duplicate, an invalid or reserved name shows the message, Cancel leaves nothing, Enter does not save the note), and both languages.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
- Headless-browser run against the real page with a stubbed API: all category interactions, both languages
#### Manual Verification
- Create and edit notes with categories; the filter narrows the list with one click and clearing restores it; it combines with search and tags
- Add a new category from the add form and from the edit form without leaving it; typing an existing name selects that category
- Counts stay right after creating, moving and deleting notes
- Existing notes appear under "Bez kategorii" / "Uncategorized"

---

## Phase 3: Managing categories

### Changes Required
#### 1. `src/compass/i18n.py` and `src/compass/page.py`
**Intent**: A window to add, rename and delete categories.
**Contract**: the "Zarządzaj" button next to the "Kategorie" heading opens an accessible dialog (`role="dialog"`, `aria-modal`, labelled, closes with Esc and the close button, focus moves in and returns). Content: an add field with a button; one row per category with its name and note count; the default row is shown fixed without actions; each other row has "Rename" (the name becomes an input with Save and Cancel) and "Delete" (a two-step confirmation like the one for notes). Errors map from `detail.code` to the translated messages added in Phase 2 (`name_invalid`, `name_reserved`, `name_taken`, `default_category`, `not_empty` showing the note count, `not_found`) and are shown in the dialog; unlike the quick add in the note form, a name that already exists is an error here. After every change the side panel's categories reload and the notes list reloads (names are shown on cards); renaming or deleting the selected category keeps the filter pointed at it or drops it when it is gone.
#### 2. `tests/`
**Intent**: Test the dialog and the error texts.
**Contract**: page smoke test for the dialog markup keys; the stubbed-API Chromium run covers add, rename, rename conflict, delete of an empty category, delete refused when not empty, the default row having no actions, Esc closing, and both languages.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
- Headless-browser run for the management dialog, both languages
#### Manual Verification
- Add, rename and delete categories in the dialog; a name that already exists and a non-empty delete show clear translated messages
- Esc and the close button close it; the side panel and cards update

---

## Phase 4: Export, import and demo

### Changes Required
#### 1. `src/compass/transfer.py`, `src/compass/notes.py`, `src/compass/api.py`
**Intent**: Carry categories through the backup and drop the format version.
**Contract**: the export document becomes `{"format": "compass-export", "exported_at", "count", "notes"}`: `EXPORT_VERSION` and the `version` field are removed, and each exported note gets `"category": <name>` (`null` for the default), placed after `tags`. `parse_export` no longer looks at a `version` (the `unsupported_version` code is removed; a file that still has the field imports, because unknown fields are ignored). In each note `category` is optional: absent or `null` means the default, a string must normalise to a valid category name, anything else is `invalid_note` with field `category`. `ParsedNote` gets `category: str | None`. `import_notes` resolves each name with `categories.ensure` inside the same transaction (creating missing categories, mapping the default's labels to the default) and still skips duplicates by title, body and creation date, leaving a skipped note's category untouched. Files made before this change (with `version: 1` and no categories) import with every note in the default.
#### 2. `src/compass/i18n.py`, `src/compass/page.py`
**Intent**: Remove the version error from the UI and add the category field name.
**Contract**: delete the `import_err_unsupported_version` translations and its entry in the page's error table; add `field_category` in both languages (used by `invalid_note`).
#### 3. `demo/compass-demo.json`, `README.md`
**Intent**: Keep the demo and docs current.
**Contract**: the demo file loses `version`, gains sensible categories (for example Bazy danych, Algorytmy, Rozmowa, Nauka, Dom) and keeps the default for a couple of notes; README's Export and Import sections drop every mention of a version, show the new example (with `category`) and say that older exports still import.
#### 4. `tests/`
**Intent**: Pin the unversioned format and compatibility.
**Contract**: `tests/test_export.py` and `tests/test_import.py` are updated (no `version` in the document, key order with `category`, the `unsupported_version` cases and the version-1 round trip assertions removed or rewritten); new tests: export lists each note's category name and `null` for the default; a round trip into an empty database reproduces notes, tags, categories and their counts (a category without notes is not exported); a file with an old `version` field and no categories imports into the default; an unknown category name is created; a name matching the default's label maps to the default; a non-string or over-long category is rejected with field `category`; a skipped duplicate keeps its category; the i18n test of import error codes drops `unsupported_version`; `tests/test_demo.py` still passes and the demo fills several categories.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
- `docker build -t compass:dev .`
#### Manual Verification
- Export, then import into a fresh instance: notes come back in the same categories
- Importing an export made before this change (it still has `version` and no categories) puts every note under "Bez kategorii" / "Uncategorized"
- Importing `demo/compass-demo.json` fills several categories

## Testing Strategy
API and migration tests (Phase 1) carry the rules; each UI phase adds page smoke tests and a Chromium run against a stubbed API in both languages; Phase 4 pins the export and import formats.

## Performance Considerations
`category_id` is indexed; the category list is one grouped query. Both are negligible at MVP volumes. The 5000-note timing tests must stay green.

## Migration Notes
Existing databases migrate on the first connection: the column is added with default 1 and the default category row is created; no data is changed. The migration is one-way: older code that reads the same database ignores the new column. Export files made after this change have no `version` field, so a Compass from before this change (which requires `version: 1`) would refuse them.

## Open Risks & Assumptions
- `notes.category_id` has no database-level foreign key (SQLite cannot add one with a `NOT NULL DEFAULT` column); the code and tests enforce it.
- A typo in a category name is fixed by renaming it (names are unique ignoring case and diacritics, so a rename onto an existing name is refused and merging means moving notes by hand).
- Deleting a category requires emptying it first; there is no bulk move.
- Quick add creates the category immediately (before the note is saved), so cancelling the note form leaves an empty category behind; the management window removes it.
- Old clients that never send a category get the default; `PUT` without a category resets a note to the default (full replacement, like tags).
- Export files made after this change are not accepted by a Compass from before it (that one requires `version: 1`); acceptable for a single-user app that always runs the latest image.

## References
- Roadmap M-02, S-03 (anchor MS-01); `context/changes/export-notes/plan.md`, `context/changes/import-notes/plan.md` (their `version` field is removed here)
- `src/compass/db.py`, `src/compass/notes.py`, `src/compass/api.py`, `src/compass/transfer.py`, `src/compass/page.py`, `src/compass/i18n.py`, `demo/compass-demo.json`

## Progress

### Phase 1: Data and API
#### Automated
- [x] 1.1 `uv run pytest` passes
- [x] 1.2 ruff check and format check pass
- [x] 1.3 mypy strict passes
#### Manual
- [x] 1.4 curl: create, count and filter by category; refused rename and non-empty delete

### Phase 2: Categories in notes and the filter
#### Automated
- [x] 2.1 `uv run pytest` passes
- [x] 2.2 ruff, format check and mypy pass
- [x] 2.3 `docker build -t compass:dev .` passes
- [x] 2.4 Headless-browser run: category field, quick add, filter, badge, counts, both languages
#### Manual
- [x] 2.5 Category choice in forms, quick add of a new category from the add and edit forms, and one-click filtering work and combine with search and tags
- [x] 2.6 Counts stay right after create, move and delete
- [x] 2.7 Existing notes appear under "Bez kategorii" / "Uncategorized"

### Phase 3: Managing categories
#### Automated
- [x] 3.1 `uv run pytest` passes
- [x] 3.2 ruff, format check and mypy pass
- [x] 3.3 `docker build -t compass:dev .` passes
- [x] 3.4 Headless-browser run for the management dialog, both languages
#### Manual
- [x] 3.5 Add, rename and delete work; conflicts and non-empty delete show translated messages
- [x] 3.6 Esc and close button work; panel and cards update

### Phase 4: Export, import and demo
#### Automated
- [x] 4.1 `uv run pytest` passes
- [x] 4.2 ruff, format check and mypy pass
- [x] 4.3 `docker build -t compass:dev .` passes
#### Manual
- [x] 4.4 Export then import into a fresh instance keeps notes in their categories
- [x] 4.5 An export made before this change (with `version`, no categories) imports into the default category
- [x] 4.6 The demo file fills several categories
