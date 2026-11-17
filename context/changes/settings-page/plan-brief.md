# S-04 settings-page — Plan Brief

> Full plan: `context/changes/settings-page/plan.md`

## What & Why
A separate Settings page that collects the configuration scattered around the app today and has room for server-side configuration later (API, LLM). (Roadmap M-02, scope anchor MS-02.)

## Starting Point
Theme, reading size/width and the list sort live in `localStorage`, the language in a cookie; import, export and the category manager crowd the sidebar; the UI is one inline script in `page.py`.

## Desired End State
`/settings` with Appearance, Data, Shortcuts and About; a server-side `settings` table with `/api/settings` (theme, reader size/width, sort); the notes page gets its theme and values from the server (no flash); import, export and category management live in Settings; the sidebar loses EN/PL and the theme switch (changed only in Settings) and gains a Settings button.

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| Sidebar | Data tools, EN/PL and theme all move to Settings (changed after testing: no duplicates) | One place for each setting, lighter sidebar |
| Storage | Server `settings` table now, partial validated updates | Foundation for API/LLM, values follow the user across devices |
| Language | Stays a cookie | Needed by the login page and the first render |
| Sections v1 | Appearance, Data, Shortcuts, About | Everything real today; no API/LLM placeholders (no dead controls) |
| Shared code | Helpers move to `core.py` used by both pages | No duplicated JS |
| Old `localStorage` values | Not migrated | Single user; one-time reset to defaults |
| Clear all data | `DELETE /api/data` reusing `notes.replace_all([], [])` | One transaction, same guarantees as import |

## Scope
In: settings store and API, about, clear data, shared JS core, `/settings` page, sidebar cleanup, docs and tests. Out: API/LLM sections, secrets, password change, tag management, language on the server, a Save button.

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 1. Store and API | `settings.py`, `/api/settings`, `/api/about`, `DELETE /api/data`, tests | Validation and atomic updates |
| 2. Shared core | `core.py`, notes page reads server settings, no flash | Regressions from moving verified code |
| 3. Settings page | Appearance, Shortcuts, About, nav, mobile | Consistent look and per-control save/revert |
| 4. Data and cleanup | Categories, import, export, clear data moved; sidebar lighter | Moving flows without losing behaviour |

**Prerequisites:** none (S-01 to S-03 done).
**Estimated effort:** ~4 sessions, 4 phases.

## Open Risks & Assumptions
- Moving `page.py` helpers touches code every flow depends on; the existing browser harnesses are the safety net.
- Preferences reset once to defaults after the upgrade.
- A settings table adds a write path to a previously read-mostly page render (one small read per page load).

## Success Criteria (Summary)
- Every Appearance control saves at once and survives reload and a second browser.
- Import, export, category management and clear data work from Settings; the sidebar no longer holds them.
- Everything that worked before still works in both languages and both themes.
