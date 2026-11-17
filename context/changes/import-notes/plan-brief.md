# S-02 import-notes — Plan Brief

> Full plan: `context/changes/import-notes/plan.md`

## What & Why
A logged-in user can load notes from an Export file back into Compass without losing title, body, tags or creation dates. It closes milestone M-02: export, then import into an empty app, must reproduce notes, tags, order and search results.

## Starting Point
S-01 produces `compass-export` version 1 files (newest first). There is no import code; `create_note` stamps "now", so import needs its own write path that keeps `created_at`, reuses tag normalisation and writes the search index.

## Desired End State
`POST /api/import` validates the whole file, then writes it in one transaction; an "Import notes" button in the side panel uploads a chosen file and shows a translated summary ("Imported n, skipped m") or a clear error. Nothing is written when any note is invalid.

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| Same note | Identical title, body and creation date (tags and id ignored) | Content-based, so idempotent across instances |
| Duplicates | Skipped, existing note untouched | Chosen after noticing "overwrite" could only change tags under this identity |
| Duplicate counting | Multiset | Two identical notes in a file both import into an empty app |
| Sources | Only Compass export files (format, version 1, `count`) | Full fidelity, one path to test |
| Invalid note | Reject the whole file, name the note and field | No half-imports; nothing lost |
| Confirmation | None; import additive, summary shown | Fewer clicks; nothing is overwritten |
| Order and dates | Oldest first, `created_at` kept, new ids | List looks the same after a round trip |
| Errors | API codes, translated in the page | Works in PL and EN |

## Scope
In: `transfer.py` validation, `notes.import_notes`, `POST /api/import`, button, translations, tests incl. a round trip, README. Out: other formats, overwrite or tag merge, partial import, preview, undo, keeping ids.

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 1. Import API | Validation, atomic write, round-trip tests | Fidelity of the round trip; duplicate rule |
| 2. Import button | File picker, summary and translated errors | Browser file handling; error messages |

**Prerequisites:** S-01 done.
**Estimated effort:** ~1-2 sessions, 2 phases.

## Open Risks & Assumptions
- A note edited after export comes back as an extra note (the old version), by design.
- Tags of a skipped duplicate are not merged.
- No undo for an import; ids are not preserved.

## Success Criteria (Summary)
- Export then import into an empty app reproduces notes, tags, dates, order and search results.
- Importing the same file twice duplicates nothing; a broken file changes nothing.
