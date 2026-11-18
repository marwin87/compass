---
project: "Compass: AI features"
context_type: brownfield
created: 2026-11-18
timeline_budget:
  delivery_weeks: 6
  hard_deadline: null
  after_hours_only: true
product_type: web-app
target_scale:
  users: small
updated: 2026-11-18
checkpoint:
  current_phase: 8
  phases_completed: [1, 2, 3, 4, 5, 6, 7]
  gray_areas_resolved:
    - topic: "original file after import"
      decision: "only the extracted text is kept; the original PDF/Word/Excel is not stored (consistent with PRD Non-Goals: no PDFs in notes)"
    - topic: "privacy"
      decision: "stays: with AI disabled no note content leaves the server; AI is optional and enabled in Settings; the UI says content goes to the model provider once enabled"
    - topic: "first slice (north star)"
      decision: "note translation (chosen over smart import, which the user named as most important; smart import follows)"
    - topic: "auth"
      decision: "no change: one password, no roles"
    - topic: "AI provider key"
      decision: "API key lives in an environment variable (.env), never in the UI or database; without the key the AI switch in Settings cannot be turned on"
    - topic: "import scope"
      decision: "file import splits one file into many topics; each becomes a proposed note with category and tags (existing first, new only if none fits); the user approves the list before anything is saved; one milestone, with translation first"
    - topic: "translation first slice"
      decision: "preview only, PL<->EN only (more languages possible later), nothing is saved; the preview can be copied to the clipboard; fits in 3 weeks of after-hours work"
  frs_drafted: 12
  quality_check_status: accepted
---

# Shape notes

Seed: add AI features to the existing Compass app (parked in `roadmap.md` as "AI features — PRD Non-Goals for the MVP"). The earlier greenfield shape session is archived in `context/foundation/archive/shape-notes-2026-11-18-0851.md`; its `Forward: rag` and `Forward: technical-roadmap` blocks (stages A1–A10) are input material, not settled decisions.

## Current System

Compass: a single-user note app (FastAPI, SQLite) with login, notes with tags and categories, fast full-text search (typo and Polish-diacritics tolerant, relevance ranking), a Markdown reader, a Settings page, JSON export and import, Polish and English UI, run as a local Docker image. Without an LLM it is a plain note search tool.

## Vision & Problem Statement

Delta: AI raises Compass above a keyword search tool. Planned capabilities: a conversation mode over the notes, translation of a note into another language, and, most important to the user, an intelligent import from other files (PDF, MS Word, Excel). Many notes will come from such files, so the import suggests a category and tags right away and rewrites the copied text with rich-text elements so that it reads better in the app.

Must preserve: everything that exists today and the speed of search.

## User & Persona

Same as today: the user themselves, the only user. Student and programmer who keeps knowledge in many files and needs it in one place, readable and findable.

## Access Control

No changes planned — current model preserved (single user, one password, no roles). The provider API key is read from an environment variable (`.env`); if it is absent, AI cannot be enabled in Settings.

## Success Criteria

Change flow (first slice): 1. the user opens a note in the reader; 2. chooses Translate (available only when AI is enabled); 3. sees a preview of the translation, PL<->EN; 4. can copy it to the clipboard; the stored note is unchanged.

### Primary
- With AI enabled, the user translates a note PL<->EN and copies the preview, and the note in the database is unchanged.

### Secondary
- Intelligent import works on one PDF, MS Word or Excel file (extracts text, suggests category and tags, rewrites the text with rich-text elements).

### Guardrails
- Search speed is not slower than today; AI calls never block search or the notes list.
- Without an API key in `.env` the app works exactly as today; no errors, AI cannot be enabled.
- Export, import and Settings keep working; the AI switch does not break the export file or import.
- A provider failure or timeout shows a clear message and the rest of the app keeps working.
- With AI disabled no note content leaves the server (PRD NFR).

## Timeline acknowledgment

Acknowledged on 2026-11-18: 6-week MVP requires sustained dedication; user accepted.

## Functional Requirements

### AI foundation
- FR-010: User can enable AI in Settings when an API key is present in `.env`. Priority: must-have. Change: new
  > Socrates: No counter-argument; it stands as written.
- FR-011: User sees in Settings that once AI is enabled, note content is sent to the model provider. Priority: must-have. Change: new
  > Socrates: No counter-argument; it stands as written.

### Translation
- FR-012: User can translate a note PL<->EN and read a preview; nothing is saved. Priority: must-have. Change: new
  > Socrates: Counter-argument considered: "without saving, the translation is lost and paid for again." Resolution: kept as written; the concern is handled in design, not scope.
- FR-013: User can copy the translation preview to the clipboard. Priority: must-have. Change: new
  > Socrates: Counter-argument considered: "without saving, the user pastes it by hand as a new note." Resolution: kept as written; the concern is handled in design, not scope.

### Intelligent import
- FR-014: User can import a PDF, MS Word or Excel file; the file is split into topics and each topic becomes a proposed note (only the text is kept, the original file is not stored). Priority: must-have. Change: new
  > Socrates: No counter-argument; it stands as written.
- FR-015: For each proposed note the user sees a suggested category and tags, taken from existing ones first and new only when none fits. Priority: must-have. Change: new
  > Socrates: Counter-argument considered: "with hundreds of tags the list does not fit in the model request." Resolution: kept as written; the concern is handled in design, not scope.
- FR-016: The imported text is rewritten with rich-text elements (headings, lists, tables) so it reads better in the app. Priority: must-have. Change: new
  > Socrates: Counter-argument considered: "the model may change the content, not only the formatting." Resolution: kept as written; the concern is handled in design, not scope.
- FR-018: User reviews the list of proposed notes, can deselect or edit them, and only confirmed notes are saved. Priority: must-have. Change: new
  > Socrates: Counter-argument considered: "if something fails midway, the model work already paid for is lost." Resolution: kept as written; the concern is handled in design, not scope.

### Conversation
- FR-017: User can hold a conversation with the notes and get answers. Priority: must-have. Change: new
  > Socrates: Counter-argument considered: "an answer without a source is not trustworthy." Resolution: kept as written; the concern is handled in design, not scope.

### Preserved
- FR-007: User can search notes by keywords, at the speed of today. Priority: must-have. Change: preserved
- FR-008: User can search and filter notes by tags (and categories). Priority: must-have. Change: preserved
- FR-009: User can export and import their data, including categories and tags. Priority: must-have. Change: preserved

## User Stories

### US-01: User translates a note and copies the result

- **Given** a logged-in user with AI enabled
- **When** they translate a note PL<->EN
- **Then** they see and can read a preview and can copy it to the clipboard, and nothing is saved; the stored note is unchanged

#### Acceptance Criteria
- The note in the database is identical before and after the translation.
- The preview can be copied to the clipboard.

## Business Logic

The application splits a file into topics and chooses a category and tags for each one on its own.

Input: a PDF, MS Word or Excel file the user imports, plus the categories and tags that already exist in the app. Output: a list of proposed notes, one per topic, each with a suggested category and tags (existing ones first, new only when none fits) and its text rewritten with rich-text elements; nothing is saved until the user confirms. The user meets this rule at import time, when they see the proposed notes instead of one raw copy of the file.

## Constraints & Preserved Behavior

- Export format `compass-export` (JSON), `/api/notes` and search keep working unchanged; new fields only optional; old export files still import.
- The search index (`notes_fts`) and the way it is rebuilt are not changed by AI.
- No data migration: AI does not change the database schema (translation saves nothing; import creates ordinary notes).
- Preserved behavior: everything in the current app, and the speed of search.

## Non-Functional Requirements

- Search keeps answering within a fraction of a second; AI calls never block search or the notes list.
- Without an API key in `.env` the app works exactly as it does today, with no errors.
- A provider failure or timeout shows a clear message and the rest of the app keeps working.
- With AI disabled, no note content leaves the server (unchanged from the PRD).

## Product framing

- `product_type`: no change — existing web-app.
- `target_scale`: no change — small (one person).
- `timeline_budget`: delivery_weeks 6, no hard deadline, after-hours only.

## Non-Goals

- Storing the original file or images from imported files: only the extracted text is kept; consistent with the PRD (no PDFs or images in notes).
- Saving a translation as a note: the translation is a preview that can be copied to the clipboard, nothing more.

## Quality cross-check

All required elements are present (access control, one-sentence business rule, timeline acknowledged at 6 weeks, non-goals, preserved behavior). No gaps. Notes for /10x-prd: the existing PRD Non-Goal "AI features" must be removed (FR-010 to FR-018 replace it); FR-017 (conversation, RAG) is the costliest item and should be its own late slice.

## Forward: tech-stack

- AI provider key from an environment variable (`.env`); the earlier session named OpenRouter for LLM and embeddings.
- Conversation over notes (FR-017) needs retrieval; the earlier session's `Forward: rag` block (archived shape notes) describes a full RAG flow as input material.
