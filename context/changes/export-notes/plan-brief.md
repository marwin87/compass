# S-01 export-notes — Plan Brief

> Full plan: `context/changes/export-notes/plan.md`

## What & Why
A logged-in user can download all their notes, with tags and creation dates, as one JSON file. It is a backup on its own (FR-009 export half, "no data loss" guardrail) and it fixes the file format that import (S-02) will read.

## Starting Point
Notes, tags, ranked search, edit/delete, login and a bilingual panel UI exist. Nothing reads the whole database: `list_notes` is capped at 50 and ranked, and there is no export code or button.

## Desired End State
`GET /api/export` downloads `compass-export-<date>.json` with every note (newest first), its tags and creation date. An "Export notes" button in the side panel triggers it. Empty database gives a valid empty file.

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| Format | One JSON file (`format`, `version`, `exported_at`, `count`, `notes`) | Lossless and easy to read back; settles PRD open question 3 |
| Scope | Always all notes, ignoring search and tag filter | A real backup, not a partial copy |
| Empty database | Valid file with an empty list | One behaviour, no special cases |
| Order | Newest first (like the app's list) | User choice; S-02 imports oldest first to keep relative order |
| Query | One `JOIN` + `group_concat`, no limit | `list_notes` is capped and ranked |
| Download | Plain `<a download>` link | No JS; the 401 guard already protects `/api/*` |

## Scope
In: `export_all()`, `GET /api/export`, the button, i18n keys, tests, README. Out: import (S-02), other formats, filtered export, streaming, encryption, `updated_at`.

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 1. Export endpoint | Query, endpoint, format tests | Exporting every note correctly (>50, unicode, tags) |
| 2. Export button | Panel button in PL/EN, README | Expired session shows 401 text instead of a file |

**Prerequisites:** M-01 done.
**Estimated effort:** ~1 session, 2 phases.

## Open Risks & Assumptions
- The file is plain text with all notes: protect it like the database.
- S-02 must import oldest first and not rely on exported ids.

## Success Criteria (Summary)
- The downloaded file contains every note with tags and dates, unchanged Polish letters, newest first.
- Works for 0 notes and for more than 50.
