---
project: "Compass: AI features"
version: 1
status: draft
created: 2026-11-18
context_type: brownfield
product_type: web-app
target_scale:
  users: small
  qps: # TODO: target_scale.qps — see Open Questions
  data_volume: # TODO: target_scale.data_volume — see Open Questions
timeline_budget:
  delivery_weeks: 6
  hard_deadline: null
  after_hours_only: true
---

## Current System Overview

Compass is a single-user note app (FastAPI backend, SQLite database) with a login, notes with tags and categories, fast full-text search (tolerant of typos and missing Polish diacritics, ranked by relevance), a Markdown reader, a Settings page, JSON export and import, a Polish and English interface, and delivery as a locally built Docker image. Without an LLM it is a plain note search tool. This PRD extends `context/foundation/prd.md` (v1) and does not replace it.

## Problem Statement & Motivation

Delta: AI raises Compass above a keyword search tool. Planned capabilities: a conversation mode over the notes, translation of a note into another language, and, most important to the user, an intelligent import from other files (PDF, MS Word, Excel). Many notes will come from such files, so the import suggests a category and tags right away and rewrites the copied text with rich-text elements so that it reads better in the app.

Must preserve: everything that exists today and the speed of search.

## User & Persona

Same as today: the user themselves, the only user. A student and programmer who keeps knowledge in many files and needs it in one place, readable and findable.

## Success Criteria

Change flow (first slice): 1. the user opens a note in the reader; 2. chooses Translate (available only when AI is enabled); 3. sees a preview of the translation, PL<->EN; 4. can copy it to the clipboard; the stored note is unchanged.

### Primary
- With AI enabled, the user translates a note PL<->EN and copies the preview, and the note in the database is unchanged.

### Secondary
- Intelligent import works on one PDF, MS Word or Excel file (extracts text, suggests category and tags, rewrites the text with rich-text elements).

### Guardrails
- Search speed is not slower than today; AI calls never block search or the notes list.
- With AI off, or with the chosen connection not configured, the app works exactly as today; no errors, and AI features stay off.
- Export, import and Settings keep working; the AI switch does not break the export file or import.
- A provider failure or timeout shows a clear message and the rest of the app keeps working.
- With AI disabled no note content leaves the server (PRD v1 NFR).

## User Stories

### US-01: User translates a note and copies the result

- **Given** a logged-in user with AI enabled
- **When** they translate a note PL<->EN
- **Then** they see and can read a preview and can copy it to the clipboard, and nothing is saved; the stored note is unchanged

#### Acceptance Criteria
- The note in the database is identical before and after the translation.
- The preview can be copied to the clipboard.

## Scope of Change

### AI foundation
- [new] FR-010: User can switch AI on and off in Settings at any time; once on, the user chooses the connection (a hosted provider or a local model), and the app checks that the chosen connection is configured and shows what is missing; AI features stay off until it is. Priority: must-have
  > Socrates: No counter-argument; it stands as written.
  > Revised 2026-11-18: the switch is always available (earlier wording: AI could not be enabled without a key); the connection is chosen after switching on; the app is built so that a hosted provider and a local model are interchangeable and more connections can be added later.
- [new] FR-011: User sees in Settings, for the chosen connection, whether note content leaves the server: with a hosted provider it is sent to that provider, with a local model it stays on the user's own machine. Priority: must-have
  > Socrates: No counter-argument; it stands as written.
  > Revised 2026-11-18: the notice depends on the chosen connection.

### Translation
- [new] FR-012: User can translate a note PL<->EN and read a preview; nothing is saved. Priority: must-have
  > Socrates: Counter-argument considered: "without saving, the translation is lost and paid for again." Resolution: kept as written; the concern is handled in design, not scope.
- [new] FR-013: User can copy the translation preview to the clipboard. Priority: must-have
  > Socrates: Counter-argument considered: "without saving, the user pastes it by hand as a new note." Resolution: kept as written; the concern is handled in design, not scope.

### Intelligent import
- [new] FR-014: User can import a PDF, MS Word or Excel file; the file is split into topics and each topic becomes a proposed note (only the text is kept, the original file is not stored). Priority: must-have
  > Socrates: No counter-argument; it stands as written.
- [new] FR-015: For each proposed note the user sees a suggested category and tags, taken from existing ones first and new only when none fits. Priority: must-have
  > Socrates: Counter-argument considered: "with hundreds of tags the list does not fit in the model request." Resolution: kept as written; the concern is handled in design, not scope.
- [new] FR-016: The imported text is rewritten with rich-text elements (headings, lists, tables) so it reads better in the app. Priority: must-have
  > Socrates: Counter-argument considered: "the model may change the content, not only the formatting." Resolution: kept as written; the concern is handled in design, not scope.
- [new] FR-018: User reviews the list of proposed notes, can deselect or edit them, and only confirmed notes are saved. Priority: must-have
  > Socrates: Counter-argument considered: "if something fails midway, the model work already paid for is lost." Resolution: kept as written; the concern is handled in design, not scope.

- [new] FR-019: User can import an image (photo, screenshot or scan): a vision model chosen in Settings reads the text on it (tables as tables, a diagram or flow with labels as a plain-text list of its elements and connections, unreadable parts marked), and the notes go through the same split, suggest and review flow as a Word file; a picture with no text is refused with a clear message, no vision model set means no image import, and the image is not stored. Priority: should-have
  > Added 2026-11-18 with slice S-07: one image per import; the only check on the reading is the user's review of the proposed notes.

### Conversation
- [new] FR-017: User can hold a conversation with the notes: ask questions in natural language, follow up on earlier answers, and get answers written only from the notes, each naming the notes it comes from (a source can be opened); when the notes do not contain the answer, the answer says so. Conversations are saved and can be reopened or deleted. Priority: must-have
  > Socrates: Counter-argument considered: "an answer without a source is not trustworthy." Resolution: sources are part of the requirement (revised 2026-11-18); an answer cites the notes it used.
  > Revised 2026-11-18: sources, follow-up questions, "not in the notes" and saved conversations written into the requirement; delivered as slice S-06. Notes are found by meaning (embeddings) and by keywords together; with no embedding model set, by keywords alone.

### Preserved
- [preserved] FR-007: User can search notes by keywords, at the speed of today. Priority: must-have
- [preserved] FR-008: User can search and filter notes by tags (and categories). Priority: must-have
- [preserved] FR-009: User can export and import their data, including categories and tags. Priority: must-have

### Removed
- [removed] The PRD v1 Non-Goal "AI features: no LLM, search by meaning, card filling from text, or translation in the MVP" no longer applies to this scope; FR-010 to FR-018 replace it.

## Constraints & Compatibility

- The export file format `compass-export` and the notes interface keep working unchanged; any new field is optional (a note's `summary`, the file's `conversations`); old export files still import.
- Search, including the way its index is built and rebuilt, is not changed by AI.
- Notes are stored as before: translation saves nothing, and import creates ordinary notes. AI adds data next to them, never inside them: kept summaries, saved conversations, and a derived vector index of the notes (rebuilt from the notes, not exported).
- Preserved behavior: everything in the current app, and the speed of search.

## Business Logic Changes

The application splits a file into topics and chooses a category and tags for each one on its own.

Input: a PDF, MS Word or Excel file the user imports, plus the categories and tags that already exist in the app. Output: a list of proposed notes, one per topic, each with a suggested category and tags (existing ones first, new only when none fits) and its text rewritten with rich-text elements; nothing is saved until the user confirms. The user meets this rule at import time, when they see the proposed notes instead of one raw copy of the file.

The current search rule (match a query against notes and order the results) is unchanged.

## Access Control Changes

No access control changes — current model preserved (single user, one password, no roles). Secrets for a hosted connection (the key) are configured on the server and never entered in the interface or stored in the database; the other connection settings (address of a local model, model name) are set in Settings. If the chosen connection is incomplete, AI features stay off and Settings shows what is missing.

## Non-Goals

- Storing the original file or images from imported files: only the extracted text is kept; consistent with PRD v1 (no PDFs or images in notes).
- Saving a translation as a note: the translation is a preview that can be copied to the clipboard, nothing more.
- Languages other than PL and EN in translation: more languages may come later.

## Open Questions

1. **What is the expected query rate (`target_scale.qps`)?** — Not captured during shaping. Owner: user. Block: no.
2. **What is the expected data volume (`target_scale.data_volume`)?** — Not captured during shaping. Owner: user. Block: no.
3. **Should import limit the file size or show an estimated cost before starting?** — Proposed during shaping and not accepted into the requirements; large files may be slow and costly. Owner: user. Block: no.
4. **Are scanned PDFs (no extractable text) in scope?** — Not decided during shaping. Owner: user. Block: no.
5. **Is FR-017 (conversation) deliverable inside the 6-week budget together with FR-010 to FR-016 and FR-018?** — Resolved 2026-11-18: delivered (slice S-06) as the last big slice before the budget was reviewed again for the remaining file formats.
6. **Which model does conversation (FR-017) use for finding notes when the connection is a local model?** — Resolved 2026-11-18: each connection has its own embedding model, set in Settings next to the chat model. With none set, notes are found by keyword search only, and the chat still works.
