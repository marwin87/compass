# Compass

A personal knowledge base: short notes in one place, found in a fraction of a second after a few typed letters. One instance serves one person.

Status: early development (see `context/foundation/roadmap.md`). Right now the app serves a minimal page and keeps a SQLite file; login, notes and search come next.

**Stack:** Python 3.12, FastAPI, SQLite (stdlib `sqlite3`), [uv](https://docs.astral.sh/uv/).

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
uv run uvicorn compass.main:app --port 8011 --reload
```

- App: http://localhost:8011/
- Health: http://localhost:8011/health
- API docs: http://localhost:8011/docs

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
