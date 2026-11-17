# S-06 search-relevance — Plan Brief

> Full plan: `context/changes/search-relevance/plan.md`

## What & Why
Search shows the most relevant notes first and forgives typos and missing Polish letters, as the PRD's business rule demands (title above body, exact tag above a plain word, `zlozonosc` finds "złożoność"), while staying fast.

## Starting Point
FTS5 prefix search (any word) ordered by newest first; the external-content index covers title and body only, tags are not searchable as text, no folding of `ł` and no typo tolerance.

## Desired End State
Results are ordered by: words matched, then field (exact tag > title > body), then exactness (exact > prefix > typo), then newest. Matching ignores case and diacritics on both sides; typos are tolerated (1 edit for 4-7 letters, 2 for 8+). Tag words are searchable.

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| Order | exact tag > title > body | Both PRD rules, literally |
| Field vs exactness | Field first, exactness inside the field | "Title above body" always holds |
| Several words | Number of words matched first, then field | Mimics AND without dropping partial hits |
| Ties | Newer note first | Consistent with the empty-query list |
| Typos | Vocabulary terms within edit distance, no new dependency | Real tolerance, testable |
| Strength | 1 edit (4-7 letters), 2 edits (8+), none under 4 | Avoids junk hits on `sql`, `api` |
| Fuzzy hits | Always included, ranked last in their field | One predictable behaviour |
| Index | Regular FTS5 table with folded title/body/tags + one-off migration | `ł→l` needs folded text; simpler writes |

## Scope
In: folding, tag search, ranking key, typo tolerance, index migration, tests incl. timing. Out: highlighting, stemming, query operators, "did you mean", caching.

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 1. Folded index with tags | Diacritic-blind search, tags searchable, migration | Migrating existing databases safely |
| 2. Relevance ranking | Ordered results per the key | Candidate cut by bm25 hiding a relevant note |
| 3. Typo tolerance | Fuzzy expansion + speed test | Vocabulary scan cost; noisy fuzzy hits |

**Prerequisites:** S-02 and S-05 done (S-03/S-04 also, they write the index).
**Estimated effort:** ~2-3 sessions, 3 phases.

## Open Risks & Assumptions
- Weights, edit limits and candidate cap are initial guesses; tune with real notes.
- Polish inflection is only approximated by prefix and typo matching.
- Rollback needs a manual FTS rebuild.

## Success Criteria (Summary)
- `zlozonosc` finds "złożoność"; `indkes` finds "indeks".
- A tagged note beats a title hit, which beats a body hit.
- Search over 5000 notes, typo included, stays well under half a second.
