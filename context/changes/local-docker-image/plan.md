# F-02 local-docker-image Implementation Plan

## Overview
Package the F-01 app as a Docker image built locally, with SQLite data on a named volume that survives container restarts and rebuilt images. Publishing to a GitHub package is a later step.

## Current State Analysis
- No `Dockerfile`, `.dockerignore`, compose file or `scripts/` yet.
- App: `src/compass/main.py` (`/`, `/health`), DB path from `COMPASS_DB_PATH` (default `data/compass.db`) in `src/compass/db.py`; the DB file is created at app startup (lifespan).
- `pyproject.toml` uses `uv_build` (package installed by `uv sync`), Python >=3.12, `uv.lock` present.
- CI (`.github/workflows/ci.yml`) has `guard` and `check` jobs; no docker job. `data/` is gitignored.

## Desired End State
`docker compose up --build` serves `/` and `/health` on port 8011; the DB lives at `/data/compass.db` on a named volume; a restart and a rebuild keep the data. CI builds the image on every PR.

## What We're NOT Doing
Publishing to GHCR or any registry, any hosting platform (no Fly), HTTPS/reverse proxy, login (S-01), frontend build, multi-arch images, log/metrics setup.

## Implementation Approach
Multi-stage build with uv; non-root runtime user owning `/data`; compose for a one-command run; persistence is checked by hand via `docker compose down` / `down -v`; CI only builds the image.

## Phase 1: Image and compose

### Changes Required
#### 1. `Dockerfile`
**Intent**: Multi-stage image: builder stage (uv image, `uv sync --locked --no-dev --no-editable` (editable would point at a missing /app/src in runtime), deps layer cached before copying `src/`), runtime stage `python:3.12-slim` with only the `.venv`.
**Contract**: non-root user `app`; `/data` owned by `app`, `VOLUME /data`; `ENV COMPASS_DB_PATH=/data/compass.db`; `EXPOSE 8011`; `CMD uvicorn compass.main:app --host 0.0.0.0 --port 8011`; `HEALTHCHECK` hitting `/health` using the Python stdlib (no curl in slim).
#### 2. `.dockerignore`
**Intent**: keep the build context small and secrets out.
**Contract**: excludes `.git`, `.venv`, `data/`, `.env*`, caches, `context/`, `.idea`.
#### 3. `docker-compose.yml`
**Intent**: one-command local run.
**Contract**: single service `compass`, `build: .`, port `8011:8011`, named volume `compass-data` mounted at `/data`.

### Success Criteria
#### Automated Verification
- Image builds: `docker build -t compass:dev .`
- Compose config valid: `docker compose config -q`
#### Manual Verification
- `docker compose up --build` serves `/` and `/health` on 8011
- Process runs as non-root (`docker compose exec compass id`)
- Container reports healthy in `docker ps`

---

## Phase 2: CI build and dev workflow

### Changes Required
#### 1. `.github/workflows/ci.yml`
**Intent**: catch Dockerfile regressions.
**Contract**: new job `docker` (ubuntu, checkout, `docker build .`); no push.

### Dev workflow (no script)
- Restart everything, keep data: `docker compose down && docker compose up --build`
- Wipe the database and restart: `docker compose down -v && docker compose up --build`

### Success Criteria
#### Automated Verification
- CI `docker` job passes on the PR
#### Manual Verification
- After `down` + `up --build` a row written to the DB is still there
- After `down -v` + `up --build` the DB is empty

---

## Testing Strategy
No new pytest tests (app code unchanged); persistence is checked manually with the two compose workflows above. Existing `uv run pytest` must stay green.

## Open Risks & Assumptions
- Bind mounts from the host may need uid alignment with `app`; named volume is the supported path.
- `uv` base image tag should be pinned to a version at least a few weeks old.

## References
- Roadmap: `context/foundation/roadmap.md` (F-02)
- App code: `src/compass/db.py`, `src/compass/main.py`

## Progress

### Phase 1: Image and compose
#### Automated
- [x] 1.1 Image builds: `docker build -t compass:dev .`
- [x] 1.2 Compose config valid: `docker compose config -q`
#### Manual
- [x] 1.3 `docker compose up --build` serves `/` and `/health` on 8011
- [x] 1.4 Process runs as non-root
- [x] 1.5 Container reports healthy

### Phase 2: CI build and dev workflow
#### Automated
- [ ] 2.1 CI `docker` job passes
#### Manual
- [x] 2.2 After `down` + `up --build` data is still there
- [x] 2.3 After `down -v` + `up --build` the DB is empty
