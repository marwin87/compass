# Demo data

`compass-demo.json` is a ready-made Compass export file with 26 sample notes, their tags and categories
(Bazy danych, Algorytmy, Rozmowa, Nauka, Dom, Compass; every note has one).

- 21 plain-text notes (study notes, interview prep, a recipe, a shopping list, a few English lines).
  They are deliberately **not** Markdown, to show that old notes still read the way they always did.
- 5 Markdown notes that show the note reader:
  - *Przewodnik: Markdown w Compass*: every element (headings, lists, quotes, links, callouts, a table, code);
  - *B-drzewo od środka (długa notatka)*: a long note with sections, so the table of contents appears;
  - *Cheatsheet: Git i Docker*: Bash code blocks and a table;
  - *Python: dekoratory i generatory*: Python code with callouts;
  - *REST vs GraphQL: porównanie*: a comparison table and a numbered list.

Load it any time with **Settings → Backup → Import**. Import replaces everything in Compass
with the file (after a confirmation), so it also works as a reset to the demo state and importing it
again gives the same result. Export first if you have notes you want to keep.

Things worth trying after the import: search `zlozonosc` (no Polish letters), `indkes` (a typo),
`sql` (exact tag first, then titles), filter by the `rozmowa` tag, click a category in the side panel (manage them in Settings → Categories),
and open a Markdown note in **Reading mode** (the book icon at the top right of the note).
