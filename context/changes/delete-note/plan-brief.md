# S-04 delete-note — Plan Brief

> Full plan: `context/changes/delete-note/plan.md`

## What & Why
A logged-in user can remove a note they no longer need, and it disappears everywhere (FR-005). Deletion is irreversible, so a confirmation guards against a stray click.

## Starting Point
Notes can be created, read, searched and edited. There is no delete path, and the FTS5 external-content index would keep a deleted note's words if only the row were removed.

## Desired End State
"Usuń" in the note view asks "Na pewno usunąć?"; after confirming, the note is gone from the list, from search and from the database, and "Notatka usunięta" is shown.

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| Deletion | Permanent (row + index entry) | Roadmap: "no longer appears anywhere"; no new columns |
| Index sync | FTS5 `'delete'` with old values, one transaction | Same proven pattern as edit |
| Confirmation | Inline two-step button, no native dialog | Consistent with S-03; browser-test friendly |
| After delete | View closes, list refreshed, short message | Clear feedback |
| Missing note | API 404; UI treats it as success | Clean contract, expected end state for the user |
| Tests | Index checks: deleted words not found, others intact | Catches stale-index bug |

## Scope
In: `delete_note`, `DELETE /api/notes/{id}`, delete UI with confirmation, tests. Out: trash/undo, bulk delete, idempotent 204.

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 1. Delete API and index | `delete_note`, `DELETE`, tests | Stale FTS entries |
| 2. Delete in the UI | Button, confirmation, message, 404 handling | Confirmation flow |

**Prerequisites:** S-02 done (S-03 provides the confirmation pattern).
**Estimated effort:** ~1 session, 2 phases.

## Open Risks & Assumptions
- Irreversible; the confirmation is the only safeguard.
- SQLite may reuse a deleted note's id; nothing depends on ids today.

## Success Criteria (Summary)
- A deleted note is gone from the list, search and database.
- Declining the confirmation changes nothing.
