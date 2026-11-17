# F-01 runnable-app-skeleton — Plan

## Context
Roadmap F-01 (`context/foundation/roadmap.md`): one runnable local app that starts, serves a minimal page, and creates and keeps its SQLite file across restarts. Unlocks S-01 (login) and everything after it. Repo has only `fastapi` + `uvicorn` installed (`pyproject.toml`), no app code, no tests; CI (`.github/workflows/ci.yml`) runs ruff + pytest (exit 5 tolerated); `data/` already in `.gitignore`; AGENTS.md says docs at port 8010.

## Decisions (confirmed with user)
- Page: plain HTML from FastAPI at `/`, plus `/health`. No Next.js yet.
- DB: stdlib `sqlite3`, no ORM, no migrations.
- DB path: env `COMPASS_DB_PATH`, default `data/compass.db` (parent dir created on demand).
- Tests: pytest with `tmp_path` (reopen DB, TestClient on `/` and `/health`).

## Not doing
Login, notes schema/tables beyond a trivial bootstrap, frontend/Next.js, Dockerfile/Fly (F-02), ORM/migrations, logging.

## Phase 1: App skeleton + persistent DB
**Files**
- `src/compass/__init__.py` (empty), `src/compass/db.py`, `src/compass/main.py`
- `tests/test_app.py`
- `pyproject.toml`: add `[tool.pytest.ini_options] pythonpath = ["src"]` (or package config) so `compass` imports in pytest and CI; add `httpx` to dev group (TestClient needs it).

**db.py** — `db_path() -> Path` (reads `COMPASS_DB_PATH`, default `data/compass.db`); `connect() -> sqlite3.Connection` (mkdir parents, open, run `CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)` so the file is really created and persistent). Fully typed (mypy strict).

**main.py** — `app = FastAPI()`; startup (lifespan) calls `connect().close()` to create the file; `GET /` → `HTMLResponse` minimal page "Compass"; `GET /health` → `{"status": "ok"}`.

**Tests** (`tests/test_app.py`): (1) with `COMPASS_DB_PATH` monkeypatched to `tmp_path`, write a row, close, reopen, row still there; (2) TestClient as context manager hits `/` (200, contains "Compass") and `/health`, and the db file exists afterwards.

### Success criteria
Automated: `uv sync`; `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src`; `uv run pytest`.
Manual: `uv run uvicorn compass.main:app --port 8010` serves `/` and `/docs`; `data/compass.db` appears; stop and restart the server, file still there with same content.

## Progress
### Phase 1: App skeleton + persistent DB
#### Automated
- [x] 1.1 ruff check + format check pass
- [x] 1.2 mypy strict passes
- [x] 1.3 pytest passes (persistence + endpoints)
#### Manual
- [x] 1.4 Server starts on 8010, `/` and `/health` respond
- [x] 1.5 `data/compass.db` survives server restart

## Process notes (on approval)
- Create `context/changes/runnable-app-skeleton/` with `change.md` (status: planned), `plan.md` (this plan in /10x-plan template) and `plan-brief.md`.
- Flip roadmap F-01 `Status: ready` → `planning` (table row + body) and bump `updated:`.
- Per CLAUDE.md: stage with `git add`, show Conventional Commit message (e.g. `feat(app): add runnable FastAPI skeleton with SQLite file`, body "Implements F-01"), no auto-commit.
