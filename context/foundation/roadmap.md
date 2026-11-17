---
project: Compass
version: 1
status: draft
created: 2026-11-17
updated: 2026-11-17
prd_version: 1
main_goal: quality
top_blocker: decisions
milestone_id: data-portability
milestone_seq: 2
milestone_status: open
---

# Roadmap: Compass

> Derived from `context/foundation/prd.md` (v1) + auto-researched codebase baseline.
> Edit-in-place; archive when superseded.
> Slices below are listed in dependency order. The "At a glance" table is the index.
> The detailed record of milestone M-01 (all foundations and slices, with their Done entries) is kept in `context/foundation/archive/2026-11-17-roadmap-first-usable-notes.md`.

## Milestone

**M-02: Data portability** — Status: open

- **Intent:** The user can take all of their notes out of Compass as a file and bring them back in, without losing a title, a body, a tag or a creation date.
- **Source materials:** `context/foundation/prd.md` (v1)
- **Done when:** every F-NN and S-NN below is `done`.
- **Scope anchors:** FR-009 (export and import of data, the PRD's only requirement not covered by M-01); PRD Success Criteria §Secondary (import and export); PRD Success Criteria §Guardrails (no data loss: a restart or failure does not delete notes).
  - MS-01: Every note belongs to a category, and the user can quickly filter the notes by category (added to M-02 by the user, 2026-11-17).

## Vision recap

Knowledge on any topic is scattered across notes, bookmarks, and memory, and finding it takes minutes. Compass keeps knowledge as short notes in one place for one person and finds them in a fraction of a second. M-01 delivered that; M-02 makes the notes portable, so they can be backed up and moved, which protects the user's knowledge from the one risk searching cannot fix: losing it.

## North star

**S-01: User can download all their notes, with tags and dates, as one file** — this is the first flow that proves data portability works: it is a usable backup on its own and it fixes the file format that import (S-02) must read back.

> "North star" here means the smallest end-to-end slice whose delivery would prove the core idea of this milestone — placed as early as Prerequisites allow, because the rest only matters if it works.

## At a glance

| ID    | Change ID    | Outcome (user can …)                                                                  | Prerequisites | PRD refs                                              | Status   |
| ----- | ------------ | ------------------------------------------------------------------------------------- | ------------- | ----------------------------------------------------- | -------- |
| S-01  | export-notes | download all my notes, with their tags and dates, as one file                         | —             | FR-009, Success Criteria §Secondary, §Guardrails      | done |
| S-02  | import-notes | load notes from an exported file back into Compass without losing title, body, tags or dates | S-01   | FR-009, Success Criteria §Secondary, §Guardrails      | done |
| S-03  | note-categories | put every note in a category and quickly filter my notes by category | — | MS-01 | done |

## Baseline

What's already in place in the codebase as of `2026-11-17` (auto-researched).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** present — one page in a panel layout (tag sidebar with counts, ranked results, note card) built from DOM calls (`src/compass/page.py`): live search with match highlighting, add, view, edit and delete with confirmation, tags and a tag filter; categories (a filter with counts in the side panel, a category field with quick add in the note forms, a "Zarządzaj" window to add, rename and delete them); a styled login page; the interface is available in Polish and English (language from the browser, PL/EN switch kept in a `lang` cookie; texts in `src/compass/i18n.py`); Export notes and Import notes buttons (download the JSON backup, load it back with a translated summary or error). UI variants are kept as standalone prototypes in `prototypes/`.
- **Backend / API:** present — FastAPI app in `src/compass/`: login, `/health`, a JSON notes API (`/api/notes`: create, read, search, edit, delete, filter by tag), `/api/tags`, `/api/categories` (list with counts, create, rename, delete), `/api/export` (JSON backup) and `/api/import` (restores it one to one: validated as a whole, then replaces all notes, tags and categories).
- **Data:** present — SQLite file (`COMPASS_DB_PATH`) with `notes` (each in a category), `tags`, `note_tags`, `categories` and a folded search index (`notes_fts`) that is rebuilt on version change; export reads all notes in one query and import writes a whole file in one transaction (creation dates kept, new ids).
- **Auth:** present — single-password login with a signed session cookie; everything except `/login` and `/health` requires it.
- **Deploy / infra:** present — local Docker image with a data volume (`Dockerfile`, `docker-compose.yml`) and a CI workflow (checks plus an image build); no registry publishing.
- **Observability:** absent — no logging or error tracking.

## Foundations

None. Every layer this milestone needs (data, API, page, login, container) is already in place, so the first slice can be planned and verified directly; see Baseline.

## Slices

### S-01: Download all notes as one file

- **Outcome:** user can download all their notes, with tags and creation dates, as one file.
- **Change ID:** export-notes
- **PRD refs:** FR-009 (export half); Success Criteria §Secondary; Success Criteria §Guardrails (no data loss)
- **Prerequisites:** —
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** — (resolved: one JSON file, `format` `compass-export`, `version` 1, newest first)
- **Risk:** Sequenced first because it fixes the file format that import depends on. With quality as the goal, the file must carry everything a note has (title, body, tags, creation date), otherwise a later import cannot restore it faithfully.
- **Status:** done

### S-02: Load notes from an exported file

- **Outcome:** user can load notes from an exported file back into Compass without losing title, body, tags or creation dates.
- **Change ID:** import-notes
- **PRD refs:** FR-009 (import half); Success Criteria §Secondary; Success Criteria §Guardrails (no data loss)
- **Prerequisites:** S-01
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** — (resolved at the time: a note with the same title, body and creation date is skipped, SUPERSEDED on 2026-11-17: import now replaces everything one to one, nothing is skipped; only Compass export files are accepted; a file with any invalid note is rejected as a whole)
- **Risk:** This is the milestone's quality bar: exporting and then importing the same file into an empty Compass must reproduce the notes, their tags and their search results. Duplicate notes and tag normalisation are the main traps.
- **Status:** done

### S-03: Put every note in a category and filter by it

- **Outcome:** user can put every note in a category and quickly narrow the list to the notes of one category.
- **Change ID:** note-categories
- **PRD refs:** MS-01
- **Prerequisites:** —
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** — (resolved: a managed list of categories created, renamed and deleted in a window; the built-in default "Bez kategorii" / "Uncategorized" holds notes without a category and old ones; one category filter at a time; deleting is blocked while a category has notes)
- **Risk:** It touches every place a note is created, edited, exported and imported, so the export file format and the import rules must stay compatible with files made before categories existed; "every note must have a category" also needs a rule for old notes and for import.
- **Status:** done

## Backlog Handoff

| Roadmap ID | Change ID    | Suggested issue title                          | Ready for `/10x-plan` | Notes                         |
| ---------- | ------------ | ---------------------------------------------- | --------------------- | ----------------------------- |
| S-01       | export-notes | Download all notes as one file                 | done                  | Done                          |
| S-02       | import-notes | Load notes from an exported file               | done                  | Done                          |
| S-03       | note-categories | Put every note in a category and filter by it | done                  | Done                          |

## Open Roadmap Questions

1. **What is the expected query rate for the instance?** — Owner: user. Block: roadmap-wide (does not gate any slice).
2. **What is the expected data volume?** — Owner: user. Block: roadmap-wide (does not gate any slice; larger data would affect export and import size).
3. **Which formats should export and import support?** — Resolved in S-01: one JSON file (`compass-export`). S-02 reads exactly that file. The format is not versioned (decided in S-03); `category` was added as an optional field.

## Parked

- **Multiple users, accounts, and sharing** — Why parked: PRD Non-Goals; one instance serves one person.
- **AI features** — Why parked: PRD Non-Goals for the MVP.
- **Study mode (flashcards and spaced repetition)** — Why parked: PRD Non-Goals for the MVP.
- **Advanced editing and attachments (rich-text editor, images, PDFs)** — Why parked: PRD Non-Goals for the MVP.
- **Publishing the Docker image as a GitHub package** — Why parked: not a PRD requirement; recorded in M-01 as a later step (the image is built locally for now).

## Milestone History

(Append-only. Carried forward verbatim into each successor milestone's roadmap; empty on the very first milestone. Closure entries are written by this skill's `READY_TO_CLOSE → CLOSED` transition. Format:)

- **M-<seq>: <Milestone name>** (`<milestone_id>`) — closed <YYYY-MM-DD>. <One-line outcome.>

- **M-01: First usable notes** (`first-usable-notes`) — closed 2026-11-17. A logged-in user keeps notes (title, body, tags), edits and deletes them, and finds them in a fraction of a second by keyword and tag with relevance ranking and typo tolerance; the app runs as a local Docker image with notes that survive restarts and rebuilds.

## Done

(Empty on first generation. `/10x-archive` appends an entry here — and flips that item's `Status` to `done` — when a change whose `Change ID` matches the item is archived. Do NOT pre-populate. Format:)

- **<Slice ID>: <Outcome>** — Archived <YYYY-MM-DD> → `context/archive/<YYYY-MM-DD-change-id>/`. Lesson: <pointer to lessons.md if any, or `—`>.
- **S-01: Download all notes as one file** — Done 2026-11-17 (closed in the roadmap directly, not archived) → `context/changes/export-notes/`. `GET /api/export` (and an Export notes button in the side panel) downloads every note, newest first, with tags and creation dates as one JSON file `compass-export-<date>.json` (`format` `compass-export`, `exported_at`, `count`, `notes`; the `version` field was dropped in S-03); search and tag filters do not apply; an empty database gives a valid empty file; 5000 notes export in about 0.1 s. Lesson: —.
- **S-02: Load notes from an exported file** — Done 2026-11-17 (closed in the roadmap directly, not archived) → `context/changes/import-notes/`. `POST /api/import` and an Import notes button load a Compass export file: the whole file is validated first and one invalid note rejects it (nothing is written); a note with the same title, body and creation date is skipped (counted as a multiset), existing notes are never changed; creation dates and tags are kept, ids are new, notes are added oldest first. Exporting and importing into an empty app reproduces notes, tags, order and search results; importing the same file twice adds nothing; 5000 notes import in about 0.15 s. Lesson: —.
- **(outside the roadmap) UI redesign: panel layout, variant A** — Done 2026-11-17. Not a roadmap item (no PRD anchor, no change folder); recorded here so the history is complete. The notes page and the login page were redesigned from prototype variant A; the page makes no external requests (no web fonts). Lesson: —.
- **(outside the roadmap) Interface languages: Polish and English** — Done 2026-11-17. Not a roadmap item (no PRD anchor, no change folder); recorded here so the history is complete. All UI text and the login page exist in both languages; the language follows the browser on the first visit and the PL/EN buttons remember the choice in a cookie. Notes, tags and search are not translated. Lesson: —.
- **(outside the roadmap) Demo data file** — Done 2026-11-17. Not a roadmap item (no PRD anchor, no change folder); recorded here so the history is complete. `demo/compass-demo.json` is a ready-made export file with 21 sample notes that can be loaded at any time with Import notes (importing it again changes nothing); a test keeps it a valid export. Superseded 2026-11-17: import became a one-to-one replace (no skipping, no duplicate rules). Lesson: —.
- **S-03: Put every note in a category and filter by it** — Done 2026-11-17 (closed in the roadmap directly, not archived) → `context/changes/note-categories/`. Every note belongs to exactly one category; the built-in default "Bez kategorii" / "Uncategorized" holds old notes and notes without a choice. Categories are managed in a "Zarządzaj" window (add, rename, delete; a category with notes cannot be deleted) and can also be added quickly from the add/edit note form; the side panel filters by one category at a time (with counts) and combines with search and tags; result cards show the category. `/api/categories` plus a `category_id` on notes and a `category_id` search filter. Export carries each note's `category` (`null` for the default) and a `categories` list (empty ones too); import is a one-to-one restore that replaces all notes, tags and categories (confirmed in the UI, nothing skipped, older files still accepted); the export format has no `version` any more. Demo file updated: every note has a category. Lesson: —.
