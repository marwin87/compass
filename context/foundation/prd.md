---
project: "Compass"
version: 1
status: draft
created: 2026-11-17
context_type: greenfield
product_type: web-app
target_scale:
  users: small
  qps: # TODO: target_scale.qps — see Open Questions
  data_volume: # TODO: target_scale.data_volume — see Open Questions
timeline_budget:
  mvp_weeks: 3
  hard_deadline: null
  after_hours_only: true
---

## Vision & Problem Statement

Knowledge on any topic is scattered across notes, bookmarks, and memory, and finding it when it is needed takes minutes. The user feels it while studying and in the middle of a conversation, when a concept has to be looked up fast. Today they search through their notes and bookmarks; the cost is minutes per lookup, against a target of seconds.

Insight: the pain is search speed, not storage. Instant results after a few typed letters, over knowledge kept as one concept per short card, remove the search cost that note tools and bookmarks leave in place. The product is universal: it is a knowledge base for any subject (study notes, programmer notes, or, for example, recipes), not a tool tied to one field.

## User & Persona

Primary persona: a universal person who keeps knowledge on a topic of their choice and needs to find it fast, with no role tied to a field. Examples of use (illustrative, not scope): study notes, notes for a programmer, a recipe collection.

The first and only user of the MVP is the user themselves (a student and programmer, using it for study notes and programmer notes). No other users are designed for at this point; the only consequence for the product is that it must not depend on any specific subject.

## Success Criteria

MVP flow (smallest end-to-end session): 1. the user logs in; 2. creates, reads, edits, and deletes notes (cards); 3. searches by keywords; 4. searches and filters by tags.

### Primary
- The user goes through the full flow (log in, create a note, find it by keyword and by tag) without errors.
- The user really uses the product instead of their old notes and bookmarks.

### Secondary
- Import and export of data.

### Guardrails
- Nothing can be read or changed without logging in.
- No data loss: a restart or failure does not delete notes.

## User Stories

### US-01: User creates a note with tags and finds it by keyword

- **Given** a logged-in user
- **When** they create a note with tags and then search for a keyword of that note
- **Then** the note appears in the search results

#### Acceptance Criteria
- A note created with tags is found by searching a keyword of that note.

## Functional Requirements

### Access
- FR-001: User can log in to the app with a password. Priority: must-have
  > Socrates: Counter-argument considered: "friction for a single user; a password at every entry slows down the quick glance this product exists for." Resolution: kept as written; the concern is handled in design, not scope.

### Notes
- FR-002: User can create a note (card). Priority: must-have
  > Socrates: Counter-argument considered: "too many fields discourage writing, so notes never get created." Resolution: kept as written; the concern is handled in design, not scope.
- FR-003: User can view a note. Priority: must-have
  > Socrates: Counter-argument considered: "overlaps with search results; a separate view may be redundant." Resolution: kept as written; the concern is handled in design, not scope.
- FR-004: User can edit a note. Priority: must-have
  > Socrates: Counter-argument considered: "an edit overwrites the previous content with no history, so a mistake destroys knowledge." Resolution: kept as written; the concern is handled in design, not scope.
- FR-005: User can delete a note. Priority: must-have
  > Socrates: No counter-argument; it stands as written.
- FR-006: User can assign tags to a note. Priority: must-have
  > Socrates: Counter-argument considered: "tag chaos; without tag management, duplicates (db, bazy, database) make filtering stop working." Resolution: kept as written; the concern is handled in design, not scope.

### Search
- FR-007: User can search notes by keywords. Priority: must-have
  > Socrates: No counter-argument; it stands as written.
- FR-008: User can search and filter notes by tags. Priority: must-have
  > Socrates: No counter-argument; it stands as written.

### Data portability
- FR-009: User can export and import their data. Priority: nice-to-have
  > Socrates: Counter-argument considered: "two formats are too much work for no MVP gain." Resolution: kept as written (nice-to-have); the number of formats is left open.

## Non-Functional Requirements

- A user sees matching notes within a fraction of a second of typing a few letters, and gets from starting a query to seeing the note they need in under 2 seconds.
- With AI features disabled, no note content leaves the user's server.

## Business Logic

The application matches a search query against the user's notes and orders the results.

The input is what the user types (and any tag they filter by). The output is a list of matching notes in a meaningful order: a note whose title matches the query ranks above a note where the word appears only in the body, and a note with a tag that exactly matches the query ranks above one that merely contains the word. Typos and missing Polish diacritics do not prevent a match (for example "zlozonosc" finds "złożoność").

The user meets this rule on every search: they type a few letters and see the most relevant notes first, without having to scan the list.

## Access Control

Single user. The user logs in with one password. No registration, no roles, no sharing; every capability is available to the logged-in user, and nothing is reachable without logging in.

## Non-Goals

- Multiple users, accounts, and sharing: one instance serves one person; no registration, roles, or sharing of notes.
- AI features: no LLM, search by meaning, card filling from text, or translation in the MVP.
- Study mode (flashcards and spaced repetition): not part of the MVP.
- Advanced editing and attachments: no WYSIWYG editor, no images or PDFs in notes.

## Open Questions

1. **What is the expected query rate (`target_scale.qps`)?** — Not captured during shaping. Owner: user. Block: no.
2. **What is the expected data volume (`target_scale.data_volume`)?** — Not captured during shaping. Owner: user. Block: no.
3. **Which formats should export and import support (FR-009)?** — Left open after the Socratic round ("two formats are too much work for no MVP gain"). Owner: user. By: before FR-009 is scheduled.
