# Demo data

`compass-demo.json` is a ready-made Compass export file with 54 sample notes, their tags and categories
(12 in all, e.g. Bazy danych, Programming, Zdrowie, Finance, Travel, Books, Pomysły, with Polish and English names mixed; every note has one).

- 43 plain-text notes (study notes, interview prep, health, finance, travel, books, ideas, a recipe, a shopping list, about 20 notes in English, the rest in Polish).
  They are deliberately **not** Markdown, to show that old notes still read the way they always did.
- 11 Markdown notes that show the note reader:
  - *Przewodnik: Markdown w Compass*: every element (headings, lists, quotes, links, callouts, a table, code);
  - *B-drzewo od środka (długa notatka)*: a long note with sections, so the table of contents appears;
  - *Cheatsheet: Git i Docker*: Bash code blocks and a table;
  - *Python: dekoratory i generatory*: Python code with callouts;
  - *REST vs GraphQL: porównanie*: a comparison table and a numbered list;
  - two notes that **mix Polish and English** (*Standup po angielsku*, *Release notes: wersja 2.4*), with three headings each, for trying the AI translation and its direction label (PL→EN or EN→PL) and the translated contents title;
  - four shorter ones (*Testing: the pyramid and its traps*, *Plan treningowy na 4 tygodnie*, *Compound interest*, *Atomic Habits: the key ideas*) with callouts, lists and a table.

Load it any time with **Settings → Backup → Import**. Import replaces everything in Compass
with the file (after a confirmation), so it also works as a reset to the demo state and importing it
again gives the same result. Export first if you have notes you want to keep.

Things worth trying after the import: search `zlozonosc` (no Polish letters), `indkes` (a typo),
`sql` (exact tag first, then titles), filter by the `rozmowa` tag, click a category in the side panel (manage them in Settings → Categories),
and open a Markdown note in **Reading mode** (the book icon at the top right of the note).
