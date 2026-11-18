# S-05 e2e-tests — Plan Brief

> Full plan: `context/changes/e2e-tests/plan.md`

## What & Why
Automated browser tests (Playwright for Python, in `tests/e2e/`) that drive the real app through the ten flows where the page script and the server must work together. Today the UI is verified by pytest on markup, Node unit tests for the pure JS, and throwaway scripts; nothing repeatable checks the real screens. They run **locally only**; CI is unchanged. (Roadmap M-02, scope anchor MS-03.)

## Starting Point
`tests/` holds backend tests and `tests/ui/` holds UI markup and pure-JS tests. CI runs lint, tests with coverage and a container smoke test. There is no browser test.

## Desired End State
`uv run pytest -m e2e` starts the app on a free port with a temporary database, runs about 50 browser tests in headless Chromium (or visibly with `--headed`) and leaves traces and screenshots of failures in `test-results/`. A plain `uv run pytest` (and CI) skips them and needs no browser.

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| Runner | `pytest-playwright` (Python) | One runner and one toolchain; same fixtures as the rest |
| Where they run | Local only, no CI job | User decision; CI stays fast and browser-free |
| How CI ignores them | `e2e` marker, `addopts = -m "not e2e"` | A plain `pytest` never needs Chromium; the package stays in the dev group so mypy and ruff still pass |
| Server | `uvicorn` subprocess per session, temporary database, test password | Fast and close to production; the Docker smoke test already covers the image |
| Isolation | Fresh browser context per test; data reset through `DELETE /api/data` and default settings through `PUT /api/settings` | Independent tests, no restart per test |
| Browser | Chromium only | One engine, least flakiness |
| Selectors | `getByRole` / `getByLabel` / `getByText`, no `waitForTimeout`, unique ids | Rules from `CLAUDE.md` and `/10x-e2e` |
| Visuals | No pixel comparison; screenshots and traces only on failure | Pixel tests are brittle |

## Scope
In: infrastructure and one test per flow: login, note creation and search, edit and delete, Markdown editor, reading mode, filters and sorting, settings persistence, data tools, tag and category management, mobile layout. Out: CI job, cross-browser runs, visual regression, load tests, testing the Docker image (the smoke test does).

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 0. Infrastructure and a seed test | Dependency, marker, server and reset fixtures, one passing test | Server start-up and reset reliability |
| 1. Login and access | Login, wrong password, guards, logout | Cookie handling per context |
| 2. Create and search | Add a note with tags and category, find it, typo search | Debounce and list timing |
| 3. Edit and delete | Edit with confirmation, delete with confirmation | Two-step confirmations |
| 4. Markdown editor | Toolbar, undo, preview, saved render | `execCommand` and selection in a real browser |
| 5. Reading mode | Enter, exit with Esc, contents, font size | Layout state and sticky contents |
| 6. Filters and sorting | Tag, category, combined, sort | State combinations |
| 7. Settings persistence | Theme, language, reading size survive reload | Server-side store |
| 8. Data tools | Export download, import popup, clear all | Downloads, file upload, native dialogs |
| 9. Tag and category management | Rename, merge with question, delete, search | Many row states |
| 10. Mobile layout | Menu drawer, list to detail, reading mode | Viewport and animations |

**Prerequisites:** none (S-01 to S-04 done).
**Estimated effort:** about 3 sessions, 11 phases (phases 1 to 10 are small).

## Open Risks & Assumptions
- Flaky tests are the main risk; mitigated by web-first assertions, no sleeps, reduced motion, and a fresh context per test.
- The first run needs `uv run playwright install chromium` (about 150 MB, once).
- Nothing guards these tests in CI, so they can rot; the plan keeps them one command away and documents it.

## Success Criteria (Summary)
- `uv run pytest -m e2e` passes repeatedly (three runs in a row) on a clean machine state.
- A plain `uv run pytest` and the CI jobs behave exactly as before.
