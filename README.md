# Compass

A personal knowledge base: short notes in one place, found in a fraction of a second after a few typed letters. One instance serves one person.

Status: early development (see `context/foundation/roadmap.md`). Right now you can log in with a password, save notes (title, body, tags), edit and delete them, and find them fast: results are ranked by relevance (exact tag, then title, then body), and typos and missing Polish letters are forgiven (`zlozonosc` finds "złożoność").

**Stack:** Python 3.12, FastAPI, SQLite (stdlib `sqlite3`), [uv](https://docs.astral.sh/uv/).

## Configuration

Everything except `/login` and `/health` requires logging in. The app refuses to start without these variables:

```bash
cp .env.example .env   # then set COMPASS_PASSWORD and COMPASS_SECRET_KEY
```

## Language

The interface is available in Polish and English. The first visit follows the browser's language
(anything else shows Polish); the **PL / EN** buttons switch it and remember the choice in a `lang`
cookie. Your notes, tags and search are not translated and work the same in both languages.

## Export

The **Export notes** button (or `GET /api/export` while logged in) downloads every note as one JSON
file, `compass-export-<date>.json`, whatever the search box or tag filter currently shows:

```json
{"format": "compass-export", "exported_at": "2026-11-17T15:10:19+00:00", "count": 2, "categories": ["Dom"],
 "notes": [{"id": 2, "title": "…", "body": "…", "tags": ["a", "b"], "category": "Dom", "created_at": "2026-11-17T15:10:19+00:00"}]}
```

Notes are listed newest first, tags alphabetically, in UTF-8. `category` is the category name, `null` for
"Uncategorized". The format has no version number. The file holds all your notes in plain
text, so keep it as safe as the database.

## Import

The **Import** button restores a file made by the Export button. It is a one-to-one restore, not a
merge: **everything currently in Compass (notes, tags, categories) is replaced** by the file's content,
after you confirm. Nothing is skipped and importing the same file twice gives the same result.

- only Compass export files are accepted (`"format": "compass-export"` and a `count` that matches the
  notes), anything else is refused with a message and changes nothing;
- the whole file is checked first: one invalid note (empty title, a title over 200 characters, a body
  over 20000, more than 10 tags or a tag over 30 characters, a bad date) or category (over 40 characters)
  rejects the entire file and the current data stays as it was;
- categories come from the file's `categories` list (including empty ones) and from each note's
  `category`; older exports without them import into "Uncategorized";
- creation dates are kept, ids are new, and notes are added oldest first so the list looks the same.

## Run with Docker

```bash
docker compose up --build          # app on http://localhost:8011
docker compose down && docker compose up --build      # restart everything, keep data
docker compose down -v && docker compose up --build   # wipe the database and restart
```

Data lives in the `compass-data` volume, mounted at `/data` (`COMPASS_DB_PATH=/data/compass.db`).

## Run locally

```bash
uv sync
set -a; source .env; set +a   # load COMPASS_PASSWORD and COMPASS_SECRET_KEY
uv run uvicorn compass.main:app --port 8011 --reload
```

- App: http://localhost:8011/
- Login: http://localhost:8011/login
- Health: http://localhost:8011/health (public)
- API docs: http://localhost:8011/docs (after login)

The database file defaults to `data/compass.db`; override it with `COMPASS_DB_PATH`.

## Checks

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
```

## Project docs

- `context/foundation/prd.md`: product requirements
- `context/foundation/tech-stack.md`: stack rationale
- `context/foundation/roadmap.md`: milestones and slices
- `AGENTS.md`: contributor and agent guidelines
