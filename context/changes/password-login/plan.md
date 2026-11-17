# S-01 password-login Implementation Plan

## Overview
Add single-user password login (FR-001) and make the whole app unreachable without it. One password from env, a signed session cookie, an HTML login form.

## Current State Analysis
- `src/compass/main.py`: FastAPI app with public `GET /` (HTML) and `GET /health`; lifespan creates the DB file. FastAPI also exposes `/docs`, `/redoc`, `/openapi.json` (all public today).
- `src/compass/db.py`: `connect()`, `db_path()` read `COMPASS_DB_PATH`.
- No auth libs, no sessions, no settings module. Tests (`tests/test_app.py`) hit `/` directly with `TestClient`.
- Docker `HEALTHCHECK` polls `/health` without credentials; `docker-compose.yml` has no env.

## Desired End State
Unauthenticated requests to anything except `/login` and `/health` are redirected to `/login`. Correct password sets a session cookie and redirects to `/`; wrong password re-renders the form with an error. `POST /logout` clears the session. The app refuses to start without `COMPASS_PASSWORD` and `COMPASS_SECRET_KEY`.

## What We're NOT Doing
Password hashing/storage in the DB, first-run setup screen, multiple users, password change UI, brute-force protection (explicitly declined), CSRF tokens beyond SameSite=Lax, "remember me" options, session revocation, rate limiting, 401 JSON API contract (redirect-based for now).

## Implementation Approach
- Config read once at import/startup from env; missing value raises a clear error (app refuses to start).
- Sessions via Starlette `SessionMiddleware` (signed cookie, `itsdangerous`), `https_only` off locally, `HttpOnly`, `SameSite=Lax`, ~30 days.
- A small middleware/dependency applies an allow-list (`/login`, `/health`); everything else needs `session["auth"]`.
- Password compared with `hmac.compare_digest`.

## Phase 1: Login and protection

### Changes Required
#### 1. `src/compass/config.py` (new)
**Intent**: Single place for required env settings.
**Contract**: `password()` / `secret_key()` (or a frozen settings object) read `COMPASS_PASSWORD`, `COMPASS_SECRET_KEY`; raise `RuntimeError` naming the missing variable. Typed for mypy strict.
#### 2. `src/compass/auth.py` (new)
**Intent**: Login/logout routes and the access guard.
**Contract**: `APIRouter` with `GET /login` (HTML form), `POST /login` (form field `password`; success sets `session["auth"]=True`, 303 to `/`; failure 401 with the form and an error message), `POST /logout` (clears session, 303 to `/login`). Guard middleware: allow `/login`, `/health`; otherwise 303 to `/login` when not authenticated. Must wrap `/docs`, `/redoc`, `/openapi.json` too.
#### 3. `src/compass/main.py`
**Intent**: Wire config, session middleware, router and guard; add a logout button to `/`.
**Contract**: middleware order: `SessionMiddleware` must run before the guard (guard reads `request.session`). `/health` still returns only `{"status":"ok"}`.
#### 4. `pyproject.toml` / `uv.lock`
**Intent**: add `itsdangerous` (required by `SessionMiddleware`) and `python-multipart` (form parsing).
#### 5. `tests/`
**Intent**: Cover the access guarantees.
**Contract**: `conftest.py` sets both env vars (and `COMPASS_DB_PATH`). Tests: anonymous `/`, `/docs`, `/openapi.json` redirect to `/login`; `/health` and `GET /login` are public; wrong password → 401 and still no access; right password → access to `/`; logout → access lost; app import/startup fails with a clear error when either variable is missing. Update existing `tests/test_app.py` to log in first where it hits `/`.

### Success Criteria
#### Automated Verification
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- `uv run mypy src tests`
#### Manual Verification
- In a browser: `/` redirects to the login form; right password lands on `/`; wrong password shows an error; logout returns to the form
- `/docs` is unavailable until logged in
- Starting without `COMPASS_PASSWORD` fails with a readable message

---

## Phase 2: Docker and docs

### Changes Required
#### 1. `.env.example` (new), `.gitignore`/`.dockerignore`
**Intent**: Document the required variables without committing secrets.
**Contract**: `.env.example` lists `COMPASS_PASSWORD`, `COMPASS_SECRET_KEY` with placeholders and a generation hint; `.env` stays ignored (already in both ignore files; verify).
#### 2. `docker-compose.yml`
**Intent**: Pass the variables to the container.
**Contract**: `env_file: .env` on the `compass` service.
#### 3. `README.md`
**Intent**: Explain setup (`cp .env.example .env`) for Docker and local runs, and that login is required.
#### 4. CI
**Intent**: Nothing to change unless tests need env outside conftest (they don't); confirm the docker build job still passes.

### Success Criteria
#### Automated Verification
- `docker compose config -q` (with a `.env` present)
- `docker build -t compass:dev .`
#### Manual Verification
- `docker compose up --build` with `.env`: login works at http://localhost:8011; container is healthy (`/health` public)
- `docker compose up` without `.env` fails with the readable error

## Testing Strategy
Unit/API tests via `TestClient` (Phase 1 list above). Manual browser check for the form and cookie flags (HttpOnly, SameSite=Lax).

## Open Risks & Assumptions
- Plain-text password in env (chosen over a hash); acceptable for a single-user local setup.
- No brute-force protection (chosen); revisit before any public exposure.
- Cookie not `Secure` locally; set `https_only` once the image is published behind HTTPS.
- Redirect-based unauthenticated responses; a future API/Next.js frontend may want 401 JSON.

## References
- PRD FR-001, Guardrails; Access Control
- `src/compass/main.py`, `src/compass/db.py`

## Progress

### Phase 1: Login and protection
#### Automated
- [x] 1.1 `uv run pytest` passes
- [x] 1.2 ruff check and format check pass
- [x] 1.3 mypy strict passes
#### Manual
- [x] 1.4 Browser login/logout flow works
- [x] 1.5 `/docs` unavailable until logged in
- [x] 1.6 Start without `COMPASS_PASSWORD` fails readably

### Phase 2: Docker and docs
#### Automated
- [x] 2.1 `docker compose config -q` passes with `.env`
- [x] 2.2 `docker build -t compass:dev .` passes
#### Manual
- [x] 2.3 Compose with `.env`: login works and container is healthy
- [x] 2.4 Compose without `.env` fails readably
