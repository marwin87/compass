# S-05 note-tags-filter — Plan Brief

> Full plan: `context/changes/note-tags-filter/plan.md`

## What & Why
A user can tag notes and narrow the list to notes with chosen tags (FR-006, FR-008), completing US-01 (create a note with tags, find it by keyword). Tags also give S-06 something to rank.

## Starting Point
Notes (title, body) with FTS5 search, edit and delete. No tags in schema, API or UI; the search index covers title and body only.

## Desired End State
Notes carry normalised tags. A tag bar with counts filters the list (all selected tags must match, combined with the text query); tags show on results and in the note view; add/edit forms take comma-separated tags with clickable suggestions of existing ones.

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| Storage | `tags` + `note_tags` tables, cascade, FK pragma on | Exact filter, counts in one query, no duplicates |
| Tag format | Comma-separated, lowercase, inner spaces allowed, ≤10 per note, ≤30 chars | `SQL` = `sql`; multi-word tags like the prototype |
| Multi-tag filter | AND, plus AND with the text query | Filter narrows, as in the prototype |
| Text search vs tags | Tags not searched as text in S-05 | FTS untouched; tag matching and ranking belong to S-06 |
| Filter UI | Tag bar with counts, click toggles; result tags clickable | Discoverable, no query syntax |
| Tag input | Comma field + clickable existing-tag suggestions | Cuts near-duplicates cheaply (datalist cannot complete per comma item) |
| Unused tags | Removed in the same transaction | Bar and suggestions show only tags in use |
| Tag order | Alphabetical | Join tables keep no entry order |

## Scope
In: tag tables, normalisation, tags in create/update/read, `GET /api/tags`, `tag` filter, tag UI, tests. Out: rename/merge, tags in text search or ranking, diacritics folding, OR filter, chips input, `#tag` syntax.

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 1. Tags in data and API | Schema, normalisation, filter, tag list, tests | Orphan cleanup and FK cascade correctness |
| 2. Tags in the UI | Tag inputs, tag bar, suggestions, display | Filter state vs reloads; XSS-safe rendering |

**Prerequisites:** S-02 done (S-03 and S-04 also done; tags must follow edit/delete).
**Estimated effort:** ~2 sessions, 2 phases.

## Open Risks & Assumptions
- `bazy`/`database`/`db` stay separate tags; suggestions are the only mitigation.
- A `PUT` without `tags` clears them (the UI always sends the field).

## Success Criteria (Summary)
- A note created with tags is found by a keyword and by its tags.
- Two selected tags show only notes with both; unused tags vanish from the bar.
