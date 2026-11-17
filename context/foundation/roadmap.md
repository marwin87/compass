---
project: Compass
version: 1
status: draft
created: 2026-11-17
updated: 2026-11-17
prd_version: 1
main_goal: speed
top_blocker: capacity
milestone_id: first-usable-notes
milestone_seq: 1
milestone_status: open
---

# Roadmap: Compass

> Derived from `context/foundation/prd.md` (v1) + auto-researched codebase baseline.
> Edit-in-place; archive when superseded.
> Slices below are listed in dependency order. The "At a glance" table is the index.

## Milestone

**M-01: First usable notes** — Status: open

- **Intent:** A logged-in user can keep notes, find them again quickly by keyword and by tag, and the app runs as a local Docker image with notes that survive restarts and new images.
- **Source materials:** `context/foundation/prd.md` (v1)
- **Done when:** every F-NN and S-NN below is `done`.
- **Scope anchors:** FR-001 to FR-008 (the must-have requirements) and US-01. FR-009 (export and import) is a nice-to-have and is parked.

## Vision recap

Knowledge on any topic is scattered across notes, bookmarks, and memory, and finding it takes minutes. Compass keeps knowledge as short notes in one place and finds them in a fraction of a second after a few typed letters. It is for one person on their own instance, usable for any subject.

## North star

**S-02: User can save a note and find it again by a keyword in it** — this is the first flow that proves the product works: it is the only user story in the PRD and the main success criterion, and `speed` as the goal means it should land as early as its prerequisites allow.

> "North star" here means the smallest end-to-end slice whose delivery would prove the core product idea — placed as early as Prerequisites allow, because everything else only matters if this works.

## At a glance

| ID    | Change ID              | Outcome (user can …)                                              | Prerequisites | PRD refs                          | Status   |
| ----- | ---------------------- | ----------------------------------------------------------------- | ------------- | --------------------------------- | -------- |
| F-01  | runnable-app-skeleton  | (foundation) one runnable app with a persistent database file     | —             | Success Criteria §Guardrails      | done |
| F-02  | local-docker-image     | (foundation) the app builds into a Docker image that runs locally with a durable data volume | F-01 | Success Criteria §Guardrails | done |
| S-01  | password-login         | log in with a password, and nothing is reachable without it       | F-01          | FR-001                            | done |
| S-02  | first-note-search      | save a note and find it again by a keyword in it                  | S-01, F-02    | US-01, FR-002, FR-003, FR-007     | done |
| S-03  | edit-note              | correct an existing note                                          | S-02          | FR-004                            | done |
| S-04  | delete-note            | remove a note I no longer need                                    | S-02          | FR-005                            | proposed |
| S-05  | note-tags-filter       | tag a note and filter my notes by tag                             | S-02          | US-01, FR-006, FR-008             | proposed |
| S-06  | relevant-search-results| see the most relevant notes first, even with typos or missing Polish letters | S-02, S-05 | FR-007, FR-008              | proposed |

## Streams

Navigation aid — groups items that share a Prerequisites chain. Canonical ordering still lives in the dependency graph below; this table is the proposed reading order across parallel tracks.

| Stream | Theme                 | Chain                                          | Note                                                                 |
| ------ | --------------------- | ---------------------------------------------- | -------------------------------------------------------------------- |
| A      | Notes and login       | `F-01` → `S-01` → `S-02` → `S-03` → `S-04`     | The shortest path to a usable app, which is what the `speed` goal asks for. |
| B      | Docker image          | `F-02`                                         | Runs alongside `S-01`; joins Stream A at `S-02`.                     |
| C      | Tags and relevance    | `S-05` → `S-06`                                | Starts once `S-02` is done; the relevance slice tunes what `S-02` first delivers. |

## Baseline

What's already in place in the codebase as of `2026-11-17` (auto-researched + user-confirmed).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** partial — one HTML page with inline JS (`src/compass/page.py`): live search, add note, note view, edit with confirmation; the Next.js frontend from `tech-stack.md` is not started.
- **Backend / API:** partial — FastAPI app in `src/compass/`: login, `/health`, and a JSON notes API (`/api/notes`: create, read, search, edit); no delete or tags yet.
- **Data:** partial — SQLite file (`src/compass/db.py`, `COMPASS_DB_PATH`) with `notes` and an FTS5 index (`notes_fts`); no tags table yet.
- **Auth:** present — single-password login with a signed session cookie (`src/compass/auth.py`); everything except `/login` and `/health` requires it.
- **Deploy / infra:** partial — CI workflow (`.github/workflows/ci.yml`, includes a Docker build job) and a local Docker image with a data volume (`Dockerfile`, `docker-compose.yml`); no registry publishing.
- **Observability:** absent — no logging or error tracking.

## Foundations

### F-01: Runnable app skeleton

- **Outcome:** (foundation) one runnable app exists locally: it starts, serves a minimal page, and creates and keeps its database file across restarts.
- **Change ID:** runnable-app-skeleton
- **PRD refs:** Success Criteria §Guardrails (no data loss)
- **Unlocks:** S-01 and, through it, every other slice; it is the smallest thing that lets a first user-facing slice be planned and verified.
- **Prerequisites:** —
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Kept to a minimal wiring of existing pieces; resist pre-building the data model or screens beyond what S-01 and S-02 need.
- **Status:** done

### F-02: Local Docker image

- **Outcome:** (foundation) the app builds into a Docker image that runs locally with a mounted data volume, and the data survives a container restart and a rebuilt image.
- **Change ID:** local-docker-image
- **PRD refs:** Success Criteria §Guardrails (no data loss)
- **Unlocks:** S-02, which is the first slice that stores user data and must show that notes survive a restart and a new image.
- **Prerequisites:** F-01
- **Parallel with:** S-01
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Container surprises (paths, permissions on the volume) surface late if left until the end; doing it beside S-01 keeps the first data-bearing slice honest. No remote host: publishing the image as a GitHub package and pulling it from there is a later step, not part of this milestone.
- **Status:** done

## Slices

### S-01: Log in with a password

- **Outcome:** user can log in with a password, and nothing in the app can be read or changed without logging in.
- **Change ID:** password-login
- **PRD refs:** FR-001
- **Prerequisites:** F-01
- **Parallel with:** F-02
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Sequenced first among slices because every later slice sits behind it and the guardrail "nothing without login" would otherwise be retrofitted. Friction for a single user is handled in design, per the PRD.
- **Status:** done

### S-02: Save a note and find it by a keyword

- **Outcome:** user can save a note and find it again by a keyword in it.
- **Change ID:** first-note-search
- **PRD refs:** US-01, FR-002, FR-003, FR-007
- **Prerequisites:** S-01, F-02
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** This is the north star; it ships a plain keyword match first, with ranking and typo tolerance left to S-06, so the product idea is tested before the search is tuned.
- **Status:** done

### S-03: Edit a note

- **Outcome:** user can edit an existing note and see the change saved.
- **Change ID:** edit-note
- **PRD refs:** FR-004
- **Prerequisites:** S-02
- **Parallel with:** S-04, S-05
- **Blockers:** —
- **Unknowns:** —
- **Risk:** An edit overwrites the previous content with no history (a counter-argument recorded in the PRD, kept as written); worth a clear confirmation behaviour in the plan.
- **Status:** done

### S-04: Delete a note

- **Outcome:** user can delete a note and it no longer appears anywhere.
- **Change ID:** delete-note
- **PRD refs:** FR-005
- **Prerequisites:** S-02
- **Parallel with:** S-03, S-05
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Deletion is irreversible for a single user; confirm before removing so a stray action does not destroy knowledge.
- **Status:** proposed

### S-05: Tag a note and filter by tag

- **Outcome:** user can add tags to a note and narrow the list to notes with a given tag.
- **Change ID:** note-tags-filter
- **PRD refs:** US-01, FR-006, FR-008
- **Prerequisites:** S-02
- **Parallel with:** S-03, S-04
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Without tag management, near-duplicate tags can make filtering unreliable (counter-argument recorded in the PRD). Completes the part of US-01 that creates a note with tags.
- **Status:** proposed

### S-06: Relevant search results

- **Outcome:** user sees the most relevant notes first — a title match above a body-only match, an exact tag above a plain word — and typos or missing Polish letters still find the note.
- **Change ID:** search-relevance
- **PRD refs:** FR-007, FR-008
- **Prerequisites:** S-02, S-05
- **Parallel with:** S-03, S-04
- **Blockers:** —
- **Unknowns:**
  - How is "relevant" tuned beyond the three rules in the PRD (title above body, exact tag above plain word, typo tolerance)? — Owner: user. Block: no.
- **Risk:** This slice carries the product's domain rule and the response-time expectation (a fraction of a second, under 2 seconds to the needed note); sequenced after tags so the exact-tag rule has something to rank.
- **Status:** proposed

## Backlog Handoff

| Roadmap ID | Change ID               | Suggested issue title                                   | Ready for `/10x-plan` | Notes                                  |
| ---------- | ----------------------- | ------------------------------------------------------- | --------------------- | -------------------------------------- |
| F-01       | runnable-app-skeleton   | Runnable app skeleton with a persistent database        | done                  | Done                                   |
| F-02       | local-docker-image      | Local Docker image with a durable data volume           | done                  | Done                                   |
| S-01       | password-login          | Log in with a password                                  | done                  | Done                                   |
| S-02       | first-note-search       | Save a note and find it by a keyword                    | done                  | Done                                   |
| S-03       | edit-note               | Edit a note                                             | done                  | Done                                   |
| S-04       | delete-note             | Delete a note                                           | yes                   | Run `/10x-plan delete-note`            |
| S-05       | note-tags-filter        | Tag a note and filter by tag                            | yes                   | Run `/10x-plan note-tags-filter`       |
| S-06       | search-relevance        | Relevant search results                                 | no                    | Waits for S-05                        |

## Open Roadmap Questions

1. **What is the expected query rate for the instance?** — Owner: user. Block: roadmap-wide (does not gate any slice).
2. **What is the expected data volume?** — Owner: user. Block: roadmap-wide (does not gate any slice; may inform S-06's response-time target).
3. **Which formats should export and import support?** — Owner: user. Block: none in this milestone (FR-009 is parked).

## Parked

- **FR-009: export and import of data** — Why parked: nice-to-have and the PRD's secondary success criterion; not needed for the first usable version.
- **Multiple users, accounts, and sharing** — Why parked: PRD Non-Goals; one instance serves one person.
- **AI features** — Why parked: PRD Non-Goals for the MVP.
- **Study mode (flashcards and spaced repetition)** — Why parked: PRD Non-Goals for the MVP.
- **Advanced editing and attachments (rich-text editor, images, PDFs)** — Why parked: PRD Non-Goals for the MVP.

## Milestone History

(Append-only. Carried forward verbatim into each successor milestone's roadmap; empty on the very first milestone. Closure entries are written by this skill's `READY_TO_CLOSE → CLOSED` transition. Format:)

- **M-<seq>: <Milestone name>** (`<milestone_id>`) — closed <YYYY-MM-DD>. <One-line outcome.>

## Done

(Empty on first generation. `/10x-archive` appends an entry here — and flips that item's `Status` to `done` — when a change whose `Change ID` matches the item is archived. Do NOT pre-populate. Format:)

- **<Slice ID>: <Outcome>** — Archived <YYYY-MM-DD> → `context/archive/<YYYY-MM-DD-change-id>/`. Lesson: <pointer to lessons.md if any, or `—`>.

- **F-01: Runnable app skeleton** — Done 2026-11-17 (closed in the roadmap directly, not archived) → `context/changes/runnable-app-skeleton/`. App starts, serves `/` and `/health`, and keeps its SQLite file across restarts. Lesson: —.
- **F-02: Local Docker image** — Done 2026-11-17 (closed in the roadmap directly, not archived) → `context/changes/local-docker-image/`. App builds into a Docker image (port 8011, non-root, data on the `compass-data` volume); `docker compose down` keeps data, `down -v` wipes it. The CI `docker` build job is added but has not run on GitHub yet. Lesson: —.
- **S-01: Log in with a password** — Done 2026-11-17 (closed in the roadmap directly, not archived) → `context/changes/password-login/`. Password from `COMPASS_PASSWORD`, signed session cookie, only `/login` and `/health` public; the app refuses to start without its secrets. Lesson: —.
- **S-02: Save a note and find it by a keyword** — Done 2026-11-17 (closed in the roadmap directly, not archived) → `context/changes/first-note-search/`. Notes (title and body) are saved and found by the first letters of a word (FTS5 prefix, any word matches), with live search on one page; notes survive container restarts. Lesson: —.
- **S-03: Edit a note** — Done 2026-11-17 (closed in the roadmap directly, not archived) → `context/changes/edit-note/`. `PUT /api/notes/{id}` keeps the FTS index in step (old words no longer match); the note view has an "Edytuj" form with a two-step overwrite confirmation; an edited note keeps its list position. Lesson: —.
