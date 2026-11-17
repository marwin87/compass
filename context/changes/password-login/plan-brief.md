# S-01 password-login — Plan Brief

> Full plan: `context/changes/password-login/plan.md`

## What & Why
Single-user login with one password (FR-001) so that nothing in the app is readable or changeable without logging in (PRD guardrail). Every later slice sits behind it.

## Starting Point
FastAPI app with public `/` and `/health` (also public `/docs`); no auth code or settings.

## Desired End State
Anonymous requests go to `/login` (except `/health`); the right password gives a 30-day session cookie; logout works; the app refuses to start without its secrets.

## Key Decisions Made
| Decision | Choice | Why |
| --- | --- | --- |
| Password | Plain-text `COMPASS_PASSWORD` env, constant-time compare | Simplest for one user; chosen over hash/DB |
| Session | Signed cookie (`SessionMiddleware`, `COMPASS_SECRET_KEY`) | No session table |
| Public paths | `/login`, `/health` only | Docker HEALTHCHECK keeps working; `/docs` protected |
| Login UX | HTML form + redirects | Works without JS; fits current page |
| Brute force | None | Declined; single user |
| Missing config | App refuses to start | No accidental unprotected run |

## Scope
In: config, login/logout, guard, tests, `.env.example`, compose env, README. Out: DB-stored password, multi-user, password change, rate limiting, JSON 401 API.

## Phases at a Glance
| Phase | Delivers | Key risk |
| --- | --- | --- |
| 1. Login and protection | Working auth + tests | Guard must cover `/docs`, `/openapi.json`; middleware order |
| 2. Docker and docs | `.env` flow in compose + README | Secrets leaking into git/image |

**Prerequisites:** F-01, F-02 done.
**Estimated effort:** ~1 session, 2 phases.

## Open Risks & Assumptions
- Plain-text password and no throttling are fine only while the instance is not exposed publicly.
- Cookie `Secure` flag is off until HTTPS exists.

## Success Criteria (Summary)
- Nothing but `/login` and `/health` is reachable without logging in.
- Login, logout and refusal to start without secrets are covered by tests.
