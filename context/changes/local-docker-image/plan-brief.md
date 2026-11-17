# F-02 local-docker-image — Plan Brief

> Full plan: `context/changes/local-docker-image/plan.md`

## What & Why
Package the F-01 app as a locally built Docker image whose SQLite data lives on a named volume. It is the base for later publishing as a GitHub package and for S-02, the first slice that stores user data.

## Starting Point
FastAPI app with `/` and `/health`, DB path from `COMPASS_DB_PATH`. No Dockerfile, compose or docker CI job.

## Desired End State
`docker compose up --build` serves the app on 8011; data survives container restart and a rebuilt image; CI builds the image.

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| Build | Multi-stage with uv, `python:3.12-slim` runtime | Small image, cached deps |
| User | non-root `app`, `/data` named volume | Safer; named volume inherits ownership |
| Compose | minimal `docker-compose.yml` | One-command run |
| Verification | Manual `compose down` / `down -v` + CI `docker build` | No extra script to maintain |

## Scope
In: Dockerfile, .dockerignore, compose, CI build job. Out: registry publishing, hosting, HTTPS, login, frontend.

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 1. Image and compose | Runnable container with volume | Volume permissions |
| 2. CI build and dev workflow | CI job; `down`/`down -v` workflow | Slow CI build |

**Prerequisites:** F-01 done, Docker installed locally.
**Estimated effort:** ~1 session, 2 phases.

## Open Risks & Assumptions
- Bind mounts may need uid alignment; named volume is the supported path.

## Success Criteria (Summary)
- App runs from the image with data on `/data`.
- `down` + `up --build` keeps data; `down -v` + `up --build` wipes it.
