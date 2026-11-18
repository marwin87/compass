<h1>
  <img src="docs/compass-icon.svg" alt="Compass icon" width="48" height="48" align="absmiddle">
  Compass
</h1>

A personal knowledge base: short notes in one place, found in a fraction of a second after a few typed letters. One instance serves one person.

Status: early development (see `context/foundation/roadmap.md`). Right now you can log in with a password, save notes (title, body, tags), edit and delete them, and find them fast: results are ranked by relevance (exact tag, then title, then body), and typos and missing Polish letters are forgiven (`zlozonosc` finds "złożoność").

**Stack:** Python 3.12, FastAPI, SQLite (stdlib `sqlite3`), [uv](https://docs.astral.sh/uv/).

## Configuration

Everything except `/login` and `/health` requires logging in. The app refuses to start without these variables:

```bash
cp .env.example .env   # then set COMPASS_PASSWORD and COMPASS_SECRET_KEY (OPENROUTER_API_KEY is optional: AI via OpenRouter)
```

## Language

The interface is available in Polish and English. The first visit follows the browser's language
(anything else shows Polish); the **PL / EN** buttons switch it and remember the choice in a `lang`
cookie. Your notes, tags and search are not translated and work the same in both languages.

## Settings

The **Settings** page (`/settings`, from the side panel) has Appearance (theme, language, reading text size and
width, default list order), Categories and Tags (search, rename, merge, delete), Backup (export and import),
Keyboard shortcuts, a Danger zone (clear all data) and About (version, counts, database size and path). Preferences are stored on the server (`GET`/`PUT /api/settings`),
so they follow you between browsers; the language is a cookie.

## Tags

Settings → Tags (also the "Zarządzaj" link next to TAGI in the side panel) manages tags across all notes at
once: search and sort the list, **rename** a tag (the new name is cleaned like any tag: lowercase, no commas,
up to 30 characters), **merge** by renaming to the name of an existing tag (Compass asks first and shows both
counts; notes that had both tags do not get a duplicate) and **delete** a tag from every note (the notes stay).
The same is available over the API: `PUT /api/tags/{name}` with `{"name": "new"}` and `DELETE /api/tags/{name}`.

## Export

The **Export notes** button (Settings → Backup, or `GET /api/export` while logged in) downloads every note as one JSON
file, `compass-export-<date>.json`, whatever the search box or tag filter currently shows:

```json
{"format": "compass-export", "exported_at": "2026-11-17T15:10:19+00:00", "count": 2, "categories": ["Dom"],
 "notes": [{"id": 2, "title": "…", "body": "…", "tags": ["a", "b"], "category": "Dom", "created_at": "2026-11-17T15:10:19+00:00"}]}
```

Notes are listed newest first, tags alphabetically, in UTF-8. `category` is the category name, `null` for
"Uncategorized". The format has no version number. The file holds all your notes in plain
text, so keep it as safe as the database.

## Import

The **Import** button (Settings → Backup) restores a file made by the Export button. It is a one-to-one restore, not a
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
uv run pytest                 # add --cov for the coverage report (CI fails below 80%)
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
```

### End-to-end tests (local only)

Browser tests of the main flows live in `tests/e2e/` (Playwright for Python). They are **not** part of a plain
`pytest` run and **not** run in CI. They start the app on a free port with a temporary database.

```bash
uv run playwright install chromium        # once (about 150 MB)
uv run pytest -m e2e                      # headless
uv run pytest -m e2e --headed --slowmo 300   # watch the browser
uv run pytest -m e2e tests/e2e/test_login.py # one module
```

A failing test leaves a screenshot and a trace in `test-results/` (`uv run playwright show-trace <trace.zip>`).

## Project docs

- `context/foundation/prd.md`: product requirements
- `context/foundation/tech-stack.md`: stack rationale
- `context/foundation/roadmap.md`: milestones and slices
- `AGENTS.md`: contributor and agent guidelines
