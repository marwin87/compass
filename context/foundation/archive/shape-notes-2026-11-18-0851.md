---
project: "Compass"
context_type: greenfield
created: 2026-11-17
updated: 2026-11-17
checkpoint:
  current_phase: 8
  phases_completed: [1, 2, 3, 4, 5, 6, 7]
  gray_areas_resolved:
    - topic: "pain category"
      decision: "data trapped in different places (notes, bookmarks, memory)"
    - topic: "insight"
      decision: "search speed (instant results after a few letters) and one concept = one short card"
    - topic: "persona scope"
      decision: "universal person; the product is topic-agnostic; the user is the first and only MVP user"
    - topic: "other users"
      decision: "for now only the user; the product only needs to be topic-agnostic (e.g. recipes would work), nothing else is designed for other users"
    - topic: "access model"
      decision: "single user, logging in with one password; no registration, no roles"
    - topic: "MVP flow"
      decision: "log in, CRUD of notes (cards), search by keywords, search/filter by tags; nothing else in the MVP"
    - topic: "MVP timeline"
      decision: "fits in 3 weeks of after-hours work; no timeline acknowledgment needed"
    - topic: "domain rule"
      decision: "the app matches a query against notes and orders the results (title match above body; exact tag above plain word; typos and missing Polish diacritics still match)"
    - topic: "non-functional properties"
      decision: "fast search (fraction of a second; under 2 s to the needed note) and no note content leaving the server when AI is off"
  frs_drafted: 9
  quality_check_status: accepted
---

# Shape notes

Seed: a user-written project specification, read in full at the start of the session; the decisions taken from it are captured in this file.

## Vision & Problem Statement

Knowledge on any topic is scattered across notes, bookmarks, and memory, and finding it when it is needed takes minutes. The user feels it while studying and in the middle of a conversation, when a concept has to be looked up fast. Today they search through their notes and bookmarks; the cost is minutes per lookup, against a target of seconds.

Insight: the pain is search speed, not storage. Instant results after a few typed letters, over knowledge kept as one concept per short card, remove the search cost that note tools and bookmarks leave in place. The product is universal: it is a knowledge base for any subject (study notes, programmer notes, or, for example, recipes), not a tool tied to one field.

## User & Persona

Primary persona: a universal person who keeps knowledge on a topic of their choice and needs to find it fast, with no role tied to a field. Examples of use (illustrative, not scope): study notes, notes for a programmer, a recipe collection.

The first and only user of the MVP is the user themselves (a student and programmer, using it for study notes and programmer notes). No other users are designed for at this point; the only consequence for the product is that it must not depend on any specific subject.

## Access Control

Single user. The user logs in with one password. No registration, no roles, no sharing; every capability is available to the logged-in user, and nothing is reachable without logging in.

## Product framing (PRD frontmatter values)

- `product_type: web-app`
- `target_scale: { users: small }`
- `timeline_budget: { mvp_weeks: 3, hard_deadline: null, after_hours_only: true }`
- Scale probe: the user does not consider a 100x scale; the product is for one person.

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

## User Stories

### US-01: User creates a note with tags and finds it by keyword

- **Given** a logged-in user
- **When** they create a note with tags and then search for a keyword of that note
- **Then** the note appears in the search results

#### Acceptance Criteria
- A note created with tags is found by searching a keyword of that note.

## Business Logic

The application matches a search query against the user's notes and orders the results.

The input is what the user types (and any tag they filter by). The output is a list of matching notes in a meaningful order: a note whose title matches the query ranks above a note where the word appears only in the body, and a note with a tag that exactly matches the query ranks above one that merely contains the word. Typos and missing Polish diacritics do not prevent a match (for example "zlozonosc" finds "złożoność").

The user meets this rule on every search: they type a few letters and see the most relevant notes first, without having to scan the list.

## Non-Functional Requirements

- A user sees matching notes within a fraction of a second of typing a few letters, and gets from starting a query to seeing the note they need in under 2 seconds.
- With AI features disabled, no note content leaves the user's server.

## Non-Goals

- Multiple users, accounts, and sharing: one instance serves one person; no registration, roles, or sharing of notes.
- AI features: no LLM, search by meaning, card filling from text, or translation in the MVP.
- Study mode (flashcards and spaced repetition): not part of the MVP.
- Advanced editing and attachments: no WYSIWYG editor, no images or PDFs in notes.

## Quality cross-check

All required elements are present (access control, one-sentence business rule, timeline within 3 weeks, non-goals). No gaps.

## Forward: tech-stack

Stack-shaped decisions the user stated up front (informational, not part of the PRD; for the tech-stack step):
- Backend in Python with FastAPI.
- Frontend in React / Next.js.
- Database: SQLite.
- Deployed as a single container with one process (multi-stage build; the Next.js frontend is a static export served by the FastAPI backend); data on a mounted volume. Chosen host: fly.
- LLM and embeddings via OpenRouter; AI features are optional and enabled only after configuration.

## Forward: rag

Informational (not part of the PRD). The user wants the full, textbook RAG flow with no shortcuts. All of it is an optional AI feature, enabled only after configuration; the core app works without it. Cards can be long (the card body has no length limit), so the whole body is indexed, not only title and summary.

Sources: cards, plus uploaded files (PDF, TXT, Markdown) stored on the data volume. Web pages are out.

Ingestion:
- Clean and normalize text; split into chunks by Markdown structure (headings, paragraphs, list items; code blocks are not cut), with a small overlap and the card title as context.
- Chunk metadata: source (card or file), domain, tags, position (for files: page).
- Embeddings per chunk through the model provider, cached by a hash of the chunk text so only changed chunks are recomputed; computed in the background through a queue with retries. Changing the embedding model invalidates old vectors.
- A short header chunk per card (title, summary, keywords) in addition to body chunks.
- Vector index kept in the same SQLite file through a vector extension (the chunk count makes a plain in-memory scan too limiting), next to the existing full-text index.
- Files: parse, extract text and pages, keep the original on the volume; size limit and no OCR.

Retrieval:
- Query processing: rewrite into a standalone question; for complex questions split into several sub-queries (fast model).
- Hybrid search: vector plus full-text, merged with reciprocal rank fusion; metadata filters (tags, domain).
- Reranking of about 30 candidates by a model scoring relevance (the provider has no dedicated reranker endpoint), then diversity selection (MMR) and aggregation of chunks to their source.

Augmentation and generation:
- Context assembly within a token budget: merge neighbouring chunks of the same source, order by relevance, deduplicate.
- Answer only from the context, with citations to source and chunk (cards by id, files by name and page); when the context is insufficient, say so and suggest which card is worth adding; streamed, cancellable; nothing is saved without the user's confirmation.

Evaluation and observability:
- A small golden set of questions with expected sources; metrics: recall@k, citation correctness, faithfulness of the answer.
- Logs: query, selected chunks, tokens, cost, duration (never the content of notes).

Consequences to carry forward:
- Privacy: the full text of cards and uploaded files goes to the model provider; the UI must say so when AI is first enabled. Uploaded files also need to be included in backups (they live on the data volume).
- The PRD non-goal "no images or PDFs in notes" concerns the MVP and notes themselves; PDFs as RAG sources are a later AI stage and should be reconciled with that non-goal when the stage is planned.
- New dependencies to justify when the stage starts: a vector extension for SQLite and a PDF text extractor.

## Forward: technical-roadmap

The user drafted a staged implementation plan (informational only; not part of the PRD). Core stages work without AI; AI stages are small, independent changes after A1.

Core:
- Stage 0: skeleton and login (project setup, backend plus static frontend, database, migrations, seed, single-user login, UI language scaffold).
- Stage 1: first deployment of the skeleton as the production container (image build, data volume, security headers, login limiter, daily backup, CI check on pull requests, manual deploy after merge).
- Stage 2: cards, CRUD, and the editor (cards, tags, domains; temporary basic search).
- Stage 3: search engine (query syntax, prefixes, Polish characters, typo tolerance, highlighting, ranking, keyboard shortcuts).
- Stage 4: tag and domain management (rename, merge, aliases, delete unused).
- Stage 5: study mode (flashcards with spaced repetition).
- Stage 6: import and export (JSON and Markdown).

AI (optional, enabled only after configuration):
- A1: AI foundation (settings, client, gating of AI routes).
- A2: indexing for RAG (chunking, embeddings, vector index); expanded, see `## Forward: rag`.
- A3: fill a card from pasted text.
- A4: tag suggestions and tag cleanup.
- A5: ask the knowledge base (full retrieval and grounded answers with citations); expanded, see `## Forward: rag`.
- A6: studying with AI (questions and answer grading).
- A7: prepare from a document (topics from a syllabus or agenda checked against the base).
- A8: translate a card on demand.
- A9: RAG quality evaluation (golden question set, metrics, logging); see `## Forward: rag`.
- A10: uploaded files as RAG sources (parsing, storage, indexing); see `## Forward: rag`.
- AI modes (for example a conversation mode): not scheduled until their behavior is defined.
