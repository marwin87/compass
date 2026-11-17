# S-03 note-categories — Plan Brief

> Full plan: `context/changes/note-categories/plan.md`

## What & Why
Every note belongs to exactly one category, and the user can filter the list by a category with one click. Categories are a managed list (create, rename, delete) kept in a window opened from the side panel. A built-in default, "Bez kategorii" / "Uncategorized", holds notes with no category. (Roadmap M-02, scope anchor MS-01.)

## Starting Point
Notes have tags (many, optional) and a ranked search; the panel has a tag bar; export writes `version: 1` and import insists on it. Nothing has a category.

## Desired End State
Mandatory `notes.category_id`; a "Kategorie" section in the side panel with counts and a one-category-at-a-time filter that ANDs with text and tags; a category field in the note forms with quick add of a new category; a management window; export with the category name, import that creates categories, and no format version at all (the `version` field is removed).

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| No category chosen | Note goes to the default "Bez kategorii" | Fast capture; the field is never empty; old notes land there too |
| Source of categories | Managed list (create, rename, delete) in a window, plus a quick "new category" option inside the add and edit note forms | User wants two places to add; an existing name just selects that category |
| Filter | One category at a time, click again clears; ANDs with text and tags | Simple and quick |
| Where | "Kategorie" section in the side panel with counts | Always visible, consistent with the tag bar |
| Delete | Blocked while the category has notes | Nothing silently rearranged |
| Rename onto an existing name | Refused with a message | No surprise merges |
| Management UI | Dialog opened from the panel | Keeps the panel uncluttered |
| Default category | Row id 1, name stored empty, label translated, not renamable or deletable; exported as `null` | Language-independent files |
| Column | `category_id NOT NULL DEFAULT 1`, no `REFERENCES` | SQLite cannot add one with foreign keys on; code and tests enforce it |
| Export/import | Add `category`; drop `version` entirely (one unversioned format); import creates unknown categories | User decision: no versioning; old files with `version` still import (extra fields ignored) |

## Scope
In: schema and migration, categories API, category in notes, filter, forms with quick add, panel section, management dialog, `category` in export and import, removing `version` from export and import, demo and README. Out: searching category names, nesting, multiple categories per note, bulk move, merging, multi-select filter, shortcuts, any format versioning.

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 1. Data and API | Schema, migration, category rules, API, tests | Migrating old databases safely |
| 2. Notes and filter UI | Form field, side-panel filter, badges, counts | Counts and filter staying in sync |
| 3. Managing categories | Dialog: add, rename, delete with translated errors | Accessible dialog behaviour |
| 4. Export, import, demo | `category` in the format, `version` removed, demo | Not breaking old files |

**Prerequisites:** S-01 and S-02 done.
**Estimated effort:** ~3-4 sessions, 4 phases.

## Open Risks & Assumptions
- No database-level foreign key on `category_id`; enforced in code and tests.
- Merging categories is manual (move notes, then delete the empty one).
- Exports made after this change are refused by a Compass from before it (it requires `version: 1`).

## Success Criteria (Summary)
- Every note has a category; one click filters by it and combines with search and tags.
- Old databases and old export files keep working, landing in "Bez kategorii".
