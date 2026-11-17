# S-03 edit-note — Plan Brief

> Full plan: `context/changes/edit-note/plan.md`

## What & Why
A logged-in user can correct an existing note (title and body) and see the change saved and searchable (FR-004).

## Starting Point
Notes can be created, read and searched; no update path. Search uses an FTS5 external-content index that a plain UPDATE would leave stale.

## Desired End State
"Edytuj" in the note view opens a prefilled form; "Zapisz" asks for confirmation before overwriting; after saving, list, view and search show the new text. The note keeps its place in the list.

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| API | `PUT /api/notes/{id}` reusing `NoteIn` | Same validation as create |
| Index sync | FTS5 `'delete'` with old values + insert, one transaction | Prevents stale search hits |
| List order | Edited note keeps its place | No new column or migration |
| UI | "Edytuj" button in the note view, Zapisz/Anuluj | Edit exactly what you see |
| Overwrite protection | Confirmation before save (inline two-step, no native dialog) | PRD risk: no history; browser-test friendly |
| Tests | API tests on the FTS index (old word gone, new found) | Catches the stale-index bug |

## Scope
In: update function, PUT endpoint, edit UI with confirmation, tests. Out: history/undo, `updated_at`, tags, delete, conflict detection, PATCH.

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 1. Update API and index | `update_note`, `PUT`, tests | Stale FTS index |
| 2. Edit in the UI | Edit form with confirmation | Confirmation flow and XSS-safe rendering |

**Prerequisites:** S-02 done.
**Estimated effort:** ~1 session, 2 phases.

## Open Risks & Assumptions
- No history: the confirmation is the only safeguard.
- Last save wins when the same note is open in two tabs.

## Success Criteria (Summary)
- An edited note shows the new text everywhere and is found by new words only.
- Cancelling, or declining the confirmation, leaves the note untouched.
