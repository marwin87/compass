# S-02 first-note-search — Plan Brief

> Full plan: `context/changes/first-note-search/plan.md`

## What & Why
North star of the product: a logged-in user saves a note (title + body), views it and finds it again by typing a few letters of a keyword. It is the first slice that proves the core idea ("find it in a fraction of a second").

## Starting Point
Login, a stub page and a SQLite file with only a `meta` table. No notes schema, no API, no search.

## Desired End State
`/` shows a search box, notes newest first, an add form and a note view. Typing filters live. Notes persist across container restarts.

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| Note fields | Title + body | Matches "one concept per card"; lets S-06 rank title above body |
| Matching | Word prefix, case-insensitive (FTS5) | "A few letters" works; no new dependency |
| Multi-word | Any word matches (OR) | User choice; ranking comes in S-06 |
| Empty query | All notes, newest first, cap 50 | Shows that saving works |
| UI | One HTML page with inline JS | No Node yet; Next.js migration later |
| API | JSON under `/api/notes`, 401 for anonymous | Clean contract for current JS and future frontend |
| Tests | API tests + one timing check (~5000 notes) | Guards the speed promise |

## Scope
In: notes table + FTS5, create/get/list/search API, live search UI, tests, persistence check. Out: tags, edit, delete, ranking, typo/diacritics tolerance, Next.js.

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 1. Notes data and API | Schema, `notes.py`, `/api/notes`, 401 guard, tests | FTS5 query sanitising; timing test flakiness |
| 2. Notes UI and persistence | Search/add/view page, Docker persistence check | XSS from note content; debounce feel |

**Prerequisites:** F-01, F-02, S-01 done.
**Estimated effort:** ~1-2 sessions, 2 phases.

## Open Risks & Assumptions
- OR queries are noisy without ranking until S-06.
- No fragment-in-word match and no `ł`→`l` folding until S-06.

## Success Criteria (Summary)
- A saved note is found by the first letters of a word in its title or body.
- Results update while typing; notes survive restart and rebuild.
