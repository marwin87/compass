---
project: Compass
version: 1
status: draft
created: 2026-11-18
updated: 2026-11-18
prd_version: 1
prd_file: prd-ai.md
main_goal: quality
top_blocker: scope
milestone_id: ai-features
milestone_seq: 3
milestone_status: open
---

# Roadmap: Compass, AI features

> Derived from `context/foundation/prd-ai.md` (v1) + the codebase baseline copied from `roadmap.md`.
> A separate roadmap, kept apart from `roadmap.md` on purpose: M-02 there stays open and this milestone runs next to it.
> `/10x-roadmap` and `/10x-archive` work on `roadmap.md` only, so statuses and Done entries here are set by hand (as "closed in the roadmap directly").
> Slices are listed in dependency order. The "At a glance" table is the index.

## Milestone

**M-03: AI features** — Status: open

- **Intent:** With an API key configured on the server and AI switched on, the user can translate a note, import notes from a PDF, MS Word or Excel file with suggested categories and tags, and talk to their notes, while search speed and everything that exists today stay unchanged.
- **Source materials:** `context/foundation/prd-ai.md` (v1); archived greenfield notes `context/foundation/archive/shape-notes-2026-11-18-0851.md` (`Forward: rag`, input material only).
- **Done when:** every F-NN and S-NN below is `done`.
- **Scope anchors:** FR-010 to FR-018 (new); FR-007, FR-008, FR-009 (preserved); Success Criteria §Guardrails (search speed, no key = app as today, provider failure handled, export and import intact).
- **Budget:** 6 weeks of after-hours work, acknowledged on 2026-11-18.

## Vision recap

Compass finds notes in a fraction of a second, but without an LLM it is a plain note search tool. M-03 lifts it: notes written in another language can be read in PL or EN, notes locked in PDF, Word and Excel files come in already split into topics with a category and tags, and the knowledge base can be asked questions with sources named.

## North star

**S-01: User can translate a note PL<->EN and copy the result** — the smallest end-to-end slice that proves the whole AI path works: a key on the server, the switch in Settings, a model call, a clear error when it fails, and the note untouched. Every later slice reuses that path.

> "North star" here means the smallest end-to-end slice whose delivery would prove the core idea of this milestone, placed as early as Prerequisites allow, because the rest only matters if it works.

## At a glance

| ID   | Change ID          | Outcome (user can …)                                                                                   | Prerequisites | PRD refs                         | Status  |
| ---- | ------------------ | ------------------------------------------------------------------------------------------------------ | ------------- | -------------------------------- | ------- |
| F-01 | ai-foundation      | switch AI on in Settings, pick OpenRouter or a local model, and see whether it is configured and whether content leaves my machine | — | FR-010, FR-011                   | done    |
| S-01 | translate-note     | translate a note PL<->EN, read the preview and copy it, with the note unchanged                        | F-01          | FR-012, FR-013, US-01            | done    |
| S-02 | import-word-file   | import one MS Word file, see it split into proposed notes, review them and save the ones I confirm      | F-01          | FR-014, FR-018                   | done    |
| S-03 | import-suggestions | see a suggested category and tags on every proposed note, taken from existing ones first               | S-02          | FR-015                           | done    |
| S-04 | import-rich-text   | get imported text rewritten with headings, lists and tables so it reads better                          | S-02          | FR-016                           | done    |
| S-05 | import-pdf-excel   | import PDF and Excel files through the same review flow                                                | S-02          | FR-014                           | pending |
| S-06 | chat-with-notes    | ask questions of my notes and get answers that name the notes they come from                           | F-01          | FR-017                           | pending |
| S-07 | import-image       | import notes from an image (photo, screenshot, scan) through the same review flow                      | S-02          | — (new, extend the PRD)          | pending |
| S-08 | import-text-file   | import notes from a plain text file (.txt, .md) through the same review flow                           | S-02          | — (new, extend the PRD)          | done    |
| S-09 | summarize-note     | get a summary and the key points of a note, kept with the note, shown above it and included in the backup | F-01       | — (new, extend the PRD)          | done    |

## Baseline

What's already in place in the codebase as of `2026-11-17` (copied from `roadmap.md`; re-check before planning the first slice).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** present — one page in a dark-first three-column layout built from DOM calls (`src/compass/ui/page.py`, reader in `src/compass/ui/reader.py`, rules in `docs/STYLE_GUIDE.md`): live search, add, view, edit, delete, tags, categories; a Settings page (`/settings`: appearance, data tools, keyboard shortcuts, about); a Markdown note reader (headings, lists, tables, callouts, highlighted code with Copy, contents) with a reading mode; toasts, skeleton loading and error states; Polish and English (texts in `src/compass/ui/i18n.py`); import, export and category management live in Settings → Data.
- **Backend / API:** present — FastAPI app in `src/compass/`: login, `/health`, `/api/notes`, `/api/tags`, `/api/categories`, `/api/settings` (server-side preferences), `/api/about`, `DELETE /api/data`, `/api/export` and `/api/import` (JSON backup of Compass only; replaces everything one to one).
- **Data:** present — SQLite file with `notes`, `tags`, `note_tags`, `categories`, `settings` and a folded search index (`notes_fts`).
- **Auth:** present — single-password login with a signed session cookie.
- **Deploy / infra:** present — local Docker image with a data volume and a CI workflow; no registry publishing.
- **Observability:** absent — no logging or error tracking (matters for provider failures and cost).
- **AI:** absent — no model client, no key handling, no Settings switch.

## Foundations

### F-01: AI foundation

- **Outcome:** user can switch AI on and off in Settings at any time; once on, the user picks the connection (OpenRouter or a local model), the app checks that the chosen connection is configured and shows what is missing, and AI features stay off until it is; the notice says whether note content leaves the machine for the chosen connection.
- **Change ID:** ai-foundation
- **PRD refs:** FR-010, FR-011; Success Criteria §Guardrails
- **Prerequisites:** —
- **Unknowns:** where in Settings the switch, the connection choice and the notice live (the page already reserves room for server-side configuration).
- **Decisions (2026-11-18):**
  - One client for every connection: OpenRouter and local servers (for example Ollama, LM Studio, llama.cpp) speak the same OpenAI-compatible protocol, so a connection is only three values: address, key, model. No class hierarchy; a new connection later is a new preset, not new code.
  - Secret in `.env` only (the OpenRouter key; a local server usually needs none, an optional key is allowed). Address and model name are set in Settings and stored on the server like the other preferences.
  - "Configured" is a static check of the required values (OpenRouter: key and model; Local: address and model). No test call, so it costs nothing; an unreachable local server shows up as a clear error on first use.
  - When the chosen connection is not configured, AI stays off and Settings lists what is missing; the app behaves exactly as today.
- **Risk:** every AI call shares this layer: a clear message on failure or timeout, no blocking of search or the notes list, and no key or note content in logs or in the export file. The on/off state and the connection settings must not leak into the export file. If it is sloppy, all later slices inherit it. Later: conversation (S-06) also needs a model for finding notes, which a local model may not offer (PRD Open Question 6).
- **Status:** done

## Slices

### S-01: Translate a note PL<->EN and copy it

- **Outcome:** user can translate a note PL<->EN, read a preview and copy it to the clipboard; nothing is saved and the stored note is unchanged.
- **Change ID:** translate-note
- **PRD refs:** FR-012, FR-013, US-01
- **Prerequisites:** F-01
- **Parallel with:** S-02
- **Blockers:** —
- **Unknowns:** how the target language is chosen (the other of PL and EN); what happens to code blocks, tables and links in the translation.
- **Risk:** the model may translate code blocks or break Markdown, and every open of the same note pays again because nothing is saved (accepted in shaping).
- **Status:** done

### S-02: Import one Word file as proposed notes

- **Outcome:** user can import one MS Word file; the file is split into topics, each topic is a proposed note, and the user reviews the list, deselects or edits entries, and only confirmed notes are saved; the original file is not stored.
- **Change ID:** import-word-file
- **PRD refs:** FR-014, FR-018
- **Prerequisites:** F-01
- **Parallel with:** S-01
- **Blockers:** —
- **Unknowns:** which format goes first (Word proposed: the simplest text to extract; the user decides); how a long file is cut into parts for the model; what happens to proposed notes if the call fails midway (Socrates: model work already paid for is lost).
- **Risk:** the biggest new surface in the milestone: file parsing, a splitting rule the app owns, and a review screen. Keep the existing JSON import (FR-009) untouched and separate.
- **Status:** done

### S-03: Suggest a category and tags for each proposed note

- **Outcome:** user sees a suggested category and tags on every proposed note, taken from existing ones first and new only when none fits. (Note titles already come from S-02; only category and tags are left.)
- **Change ID:** import-suggestions
- **PRD refs:** FR-015
- **Prerequisites:** S-02
- **Parallel with:** S-04
- **Blockers:** —
- **Unknowns:** how to send hundreds of existing tags to the model (Socrates: the list may not fit); how to avoid near-duplicates such as db / bazy / database.
- **Risk:** tag chaos in the database; the review screen is the guard, so the suggestions must be editable there.
- **Status:** done

### S-04: Rewrite imported text with rich-text elements

- **Outcome:** user gets imported text rewritten with headings, lists and tables so that it reads better in the reader. (**Largely done in S-02**: the model already writes notes as structured Markdown. Left: check on real files whether it is enough, then close or cut this slice.)
- **Change ID:** import-rich-text
- **PRD refs:** FR-016
- **Prerequisites:** S-02
- **Parallel with:** S-03
- **Blockers:** —
- **Unknowns:** how to check that the rewrite changed structure only, not meaning (Socrates: the model may change content).
- **Risk:** silent loss of detail with no original to compare, because the file is not stored; the review screen is the only check.
- **Status:** done

### S-05: Import PDF and Excel through the same flow

- **Outcome:** user can import PDF and Excel files through the same split, suggest and review flow.
- **Change ID:** import-pdf-excel
- **PRD refs:** FR-014
- **Prerequisites:** S-02
- **Parallel with:** S-06
- **Blockers:** —
- **Unknowns:** scanned PDFs (PRD Open Question 4); how a spreadsheet becomes topics (no narrative text); file size limit and cost shown before start (PRD Open Question 3).
- **Risk:** two more parsers with different failure modes; an empty extraction must end in a clear message, not in an empty list.
- **Status:** pending

### S-06: Talk to the notes with named sources

- **Outcome:** user can ask questions of their notes and get answers that name the notes they come from.
- **Change ID:** chat-with-notes
- **PRD refs:** FR-017
- **Prerequisites:** F-01
- **Parallel with:** S-05
- **Blockers:** —
- **Unknowns:** how notes are retrieved for a question (the archived `Forward: rag` block is input, not a decision); whether it fits the 6-week budget (PRD Open Question 5); what the answer says when the notes do not contain it.
- **Risk:** the costliest item. It may need an index of its own next to the search index, and content of many notes goes to the provider on every question. The search index and its rebuild must stay untouched. Expect to split it into smaller slices when planning.
- **Status:** pending

### S-07: Import notes from an image

- **Outcome:** user can import an image (photo of a page, screenshot, scan); the model reads the text on it and the notes go through the same split, review and save flow as a Word file; the image is not stored.
- **Change ID:** import-image
- **PRD refs:** — (new; add an FR to `prd-ai.md` before planning)
- **Prerequisites:** S-02
- **Parallel with:** S-08, S-09
- **Blockers:** the chosen model must accept images (vision); a local model often does not.
- **Unknowns:** how Settings tells the user whether the model can read images; accepted formats (PNG, JPG, WebP) and size limit; several images in one import; handwriting and poor photos (the check for what was missed cannot compare with a source text, so the user is the only check). The same question as scanned PDFs (PRD Open Question 4) and likely the same answer.
- **Risk:** the image goes to the provider as it is (more data and more cost than text); no source text to check against. Keep the existing stream and review code (`importer.run`, the Settings review card), add only the way the text is read.
- **Status:** pending

### S-08: Import notes from a plain text file

- **Outcome:** user can import a `.txt` or `.md` file through the same split, review and save flow as a Word file.
- **Change ID:** import-text-file
- **PRD refs:** — (new; add an FR to `prd-ai.md` before planning)
- **Prerequisites:** S-02
- **Parallel with:** S-07, S-09
- **Blockers:** —
- **Unknowns:** text encoding (UTF-8, Windows-1250); a Markdown file already has headings, so check that the model keeps them; whether the file input in Settings becomes one "import a file" control for every format.
- **Risk:** small: no new parser beyond reading the text into blocks (`docx.Block`), so the rest of the flow is reused as is.
- **Status:** done

### S-09: Summarize a note

- **Outcome:** user can ask for a summary and the key points of a note; the summary is written above the note in an AI block, kept with the note (shown again whenever it is opened, marked outdated after an edit) and carried by export and import; the note text itself is never changed.
- **Change ID:** summarize-note
- **PRD refs:** — (new; add an FR to `prd-ai.md` before planning)
- **Prerequisites:** F-01
- **Parallel with:** S-07, S-08
- **Blockers:** —
- **Unknowns:** the shape of the answer (a short paragraph plus a list of key points); the language of the summary (the note's own, or the interface language); whether a very long note is cut into parts first (reuse the windows of `importer.py`); where the control sits next to Translate (S-01).
- **Risk:** small: the same path as S-01 (`POST /api/notes/{id}/translate`, preview in the reader layout, AI marker). Like translation, every open pays again because nothing is saved.
- **Status:** done

## Backlog Handoff

| Roadmap ID | Change ID          | Suggested issue title                                   | Ready for `/10x-plan` | Notes                          |
| ---------- | ------------------ | ------------------------------------------------------- | --------------------- | ------------------------------ |
| F-01       | ai-foundation      | Add the AI switch, server-side key and provider client  | done                  | Decisions recorded in F-01     |
| S-01       | translate-note     | Translate a note PL<->EN with a copyable preview        | done                  | North star                     |
| S-02       | import-word-file   | Import a Word file as proposed notes with review        | done                  | Word first; the model writes the notes |
| S-03       | import-suggestions | Suggest category and tags for proposed notes            | done                  | Built on S-02's flow           |
| S-04       | import-rich-text   | Rewrite imported text with rich-text elements           | done                  | Delivered inside S-02          |
| S-05       | import-pdf-excel   | Import PDF and Excel files through the same flow        | after S-02            | Open: scans, size limit        |
| S-06       | chat-with-notes    | Ask questions of the notes with named sources           | after F-01            | May split; fit in budget open  |
| S-07       | import-image       | Import notes from an image through the same flow        | after S-02            | Needs a vision model; add FR   |
| S-08       | import-text-file   | Import notes from a .txt or .md file                    | done                  | FR still to add to the PRD     |
| S-09       | summarize-note     | Summarize a note (summary and key points), kept with the note | done            | FR still to add to the PRD     |

## Open Roadmap Questions

1. **Which model provider and model?** — Resolved 2026-11-18: OpenRouter or a local model through one common client; the model name is set in Settings.
2. **Which file format is imported first?** — Resolved 2026-11-18: Word (S-02 done).
3. **Are scanned PDFs in scope?** — Owner: user. Block: S-05.
4. **Should import limit file size or show an estimated cost first?** — Owner: user. Block: S-05.
5. **Does S-06 (conversation) fit in the 6-week budget with everything else?** — Owner: user. Block: roadmap-wide. S-07 to S-09 were added on 2026-11-18 after S-02; they add to the scope, so the 6 weeks need another look.
6. **Expected query rate and data volume** — Owner: user. Block: roadmap-wide (does not gate any slice).

## Parked

- **Study mode (flashcards and spaced repetition)** — Why parked: PRD v1 Non-Goals; not part of this scope.
- **Translation into languages other than PL and EN** — Why parked: `prd-ai.md` Non-Goals; more languages may come later.
- **Saving a translation as a note** — Why parked: `prd-ai.md` Non-Goals.
- **Storing the original file or images of an import** — Why parked: `prd-ai.md` Non-Goals.

## Milestone History

(Append-only. Empty: M-03 is the first milestone of this roadmap. M-01 and M-02 are recorded in `roadmap.md`.)

## Done

- **F-01: AI foundation** — Done 2026-11-18 → closed in the roadmap directly. Key is read from `OPENROUTER_API_KEY` (env only); status via `GET /api/ai/status`; no model client yet (`httpx` comes with S-01). Lesson: —.
- **S-01: Translate a note PL<->EN and copy it** — Done 2026-11-18 → closed in the roadmap directly. `POST /api/notes/{id}/translate` (stdlib client, model reply starts with `[en]`/`[pl]`), preview in the reader layout, AI marker (frame, spark icon, tag), one model per connection. Lesson: the model must name its target language, otherwise UI labels (callouts) follow the interface language.

- **S-02: Import one Word file as proposed notes** — Done 2026-11-18 → closed in the roadmap directly. `POST /api/import/word` streams one JSON line per part (`importer.run`); the model reads the file part by part and writes tidy Markdown notes (headings, lists, tables), a second call per part lists what is missing, and the code lists numbers and links found in no note. A failed part reports its reason (`AIError.detail`, e.g. `HTTP 429`) and can be run again alone (`?parts=`). Review in Settings → Backup: accordions, saving while later parts still arrive, `POST /api/notes/bulk` (all or none). Covers FR-014, FR-018, and already FR-016 (rich text, S-04) and note titles from FR-015 (S-03). Limits: 5 MB file, 100 000 characters of text. Lesson: splitting by headings in code gave poor, cut-up notes; the model has to read and write the notes itself, with a check for what it missed.

- **S-03: Suggest a category and tags for each proposed note** — Done 2026-11-18 → closed in the roadmap directly. The model returns a category and 2 to 5 tags with every note; the prompt lists the existing categories and the 150 most used tags (existing first, new only when none fits). The code maps the answer onto existing names (case and accents ignored), drops bad tags and reserved category names. The review shows an editable category field (datalist of existing ones) and a tags field, and a line naming which names are new; `POST /api/notes/bulk` takes the category by name and creates it when missing (all or none). Also shipped around it: notes stream into the review one by one while the model writes (`ai.stream`), the section moved to Settings → Load Data, and the setting "block the page during AI work" (`aiBusy`, a rule for every AI job). Known limit: parts run in parallel, so a new tag or category proposed in one part is unknown to the others. Lesson: a code-side mapping onto existing names plus a visible "new" marker is a better guard against tag chaos than prompt wording alone.

- **S-04: Rewrite imported text with rich-text elements** — Done 2026-11-18 → closed in the roadmap directly. Delivered inside S-02: the model writes every note as tidy Markdown (headings, lists, tables, fenced code) and keeps all facts. The open question (structure changed, not meaning) is covered by the check step (what the model found missing, plus numbers and links found in no note) and by the user reviewing every note before saving. Known limit: the check is done by the same model that wrote the notes, and there is no original to compare against. Lesson: a quality requirement like this was cheaper to meet inside the main flow than as a separate pass.

- **S-08: Import notes from a plain text file** — Done 2026-11-18 → closed in the roadmap directly. `.txt`, `.md` and `.markdown` go through the same flow as Word. `src/compass/textfile.py` reads blocks (blank-line paragraphs, `#` headings, a fenced code block kept whole); the endpoint became generic, `POST /api/import/file?name=…`, and `importer._blocks` picks the parser by extension (an unknown one is `unsupported`, no model call), so the next format is one parser and one line. Encodings: UTF-8 (BOM or not), then Windows-1250; text is normalised to NFC (macOS can write accented letters decomposed, which would split a tag in two); CR, LF and CRLF line endings all work. `BadDocx` became `BadFile`. Known limits: `.rtf` (TextEdit's default) is not supported, and very old MacRoman files are read as Windows-1250 without an error. Lesson: files from macOS differ from Windows ones in more than the picker (decomposed Unicode, CR line endings); test with real files from the user's own system.

- **S-09: Summarize a note** — Done 2026-11-18 → closed in the roadmap directly. `POST /api/notes/{id}/summarize` writes a short summary and 3 to 7 key points in the language of the note and **keeps** it (table `note_summaries`, one per note, `src/compass/summaries.py`; not searched, deleted with the note); `GET` and `DELETE /api/notes/{id}/summary` read and remove it. It remembers a digest of the title and text it came from, so after an edit it shows as outdated (still readable, Refresh writes a new one), also when the edit happened while the model was working. Export and import carry it as an optional `summary` field of the note (a file without summaries is unchanged, a malformed one is refused). UI: the note panel got an AI strip (Summarize, Translate; one AI tag, on the right) instead of toolbar icons; the summary opens above the note in an AI block, open by default, with Copy, Refresh, collapse and a close button that deletes it; translation is unchanged (replaces the note, not kept). Rule added for every AI job: the "block the page during AI work" setting (`aiBusy`). Known limits: one call per note (20 000 characters at most, no splitting); the answer is not streamed. Lesson: where a result has lasting value (a summary) keep it from the start, where it is a one-off preview (a translation) do not; and a layout study (`docs/prototypes/ai-note-actions.html`) before moving buttons settled the placement in one round.

(Entries are added by hand when a slice is finished, format: `- **<ID>: <Outcome>** — Done <YYYY-MM-DD> → `context/changes/<change-id>/`. Lesson: —.`)
