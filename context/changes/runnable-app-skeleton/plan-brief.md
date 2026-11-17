# F-01 Runnable app skeleton — Plan Brief

> Full plan: `context/changes/runnable-app-skeleton/plan.md`

## What & Why
A minimal FastAPI app that serves a page and creates a SQLite file that survives restarts. Unlocks S-01 (login) and all later slices.

## Key Decisions
| Decision | Choice | Why |
| --- | --- | --- |
| Page | HTML from FastAPI + `/health` | No Node needed yet |
| DB access | stdlib `sqlite3` | Zero deps; FTS5 later needs raw SQL anyway |
| DB path | `COMPASS_DB_PATH`, default `data/compass.db` | Works locally; points at a volume on Fly |
| Tests | pytest + `tmp_path` | Fast, runs in CI |

## Scope
In: `src/compass/{db,main}.py`, tests, pytest config. Out: login, notes, frontend, Docker/Fly.

## Phases
1. App skeleton + persistent DB — one phase, one session.
