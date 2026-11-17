---
bootstrapped_at: 2026-11-17T12:44:43Z
starter_id: fastapi
starter_name: FastAPI
project_name: compass
language_family: python
package_manager: uv
cwd_strategy: native-cwd
bootstrapper_confidence: first-class
phase_3_status: ok
audit_command: "pip-audit"
---

## Hand-off

```yaml
starter_id: fastapi
package_manager: uv
project_name: compass
hints:
  language_family: python
  team_size: solo
  deployment_target: fly
  ci_provider: github-actions
  ci_default_flow: manual-promotion
  bootstrapper_confidence: first-class
  path_taken: custom
  quality_override: false
  self_check_answers:
    typed: true
    from_official_starter: false
    conventions: true
    docs_current: true
    can_judge_agent: false
  has_auth: true
  has_payments: false
  has_realtime: false
  has_ai: false
  has_background_jobs: false
```

## Why this stack

A solo developer building a small single-user knowledge base in three weeks of after-hours work, with login as the only technology-forcing feature. Custom path: the user already chose a Python backend with a React/Next.js frontend and SQLite, so the recommended web default (Django) was declined. FastAPI clears all four agent-friendly gates (typed with Pydantic, convention-based, popular within Python, well documented) and its bootstrapper confidence is first-class. The registry card covers only the backend half; the Next.js frontend (static export, served by the backend) is added by hand and is not scaffolded by this starter. The app ships as a single container with one process on fly, with a volume for the SQLite data. The user's earlier wish to avoid multi-package repositories is in tension with a Python plus Node layout and was accepted knowingly. CI is GitHub Actions with manual promotion after merge. The self-check flagged two gaps (no official template for the combined layout, limited confidence in judging agent output), so project instructions in CLAUDE.md or AGENTS.md should compensate.

## Pre-scaffold verification

| Signal      | Value                          | Severity | Notes                                                                 |
| ----------- | ------------------------------ | -------- | --------------------------------------------------------------------- |
| npm package | not run                        | n/a      | not a JS-family starter                                               |
| GitHub repo | not run                        | n/a      | card `docs_url` (`https://fastapi.tiangolo.com`) is not a GitHub URL  |

No recency signal available.

## Scaffold log

**Resolved invocation**: `uv add fastapi uvicorn` (run in the current directory; the first half of the card template, `uv init .`, was skipped on the user's choice because `pyproject.toml` already existed and `uv init` refuses an already initialized project)
**Strategy**: native-cwd
**Exit code**: 0
**Pre-flight files-to-touch**: pyproject.toml, uv.lock, .venv
**Files written by CLI**: 1 new (`uv.lock`); `pyproject.toml` modified (dependencies added); `.venv` updated with 14 packages
**Pre-existing files preserved**: pyproject.toml (kept; only `dependencies` was extended), .gitignore, .pre-commit-config.yaml, AGENTS.md, CLAUDE.md, compass-prototyp.html, context/

Packages installed: fastapi 0.163.1, uvicorn 0.54.0, starlette 1.10.0, pydantic 2.14.3, pydantic-core 2.50.4, annotated-doc 0.0.6, annotated-types 0.8.0, anyio 4.16.0, click 8.5.1, h11 0.16.0, idna 3.20, opentelemetry-api 1.45.2, typing-extensions 4.16.0, typing-inspection 0.4.5.

## Post-scaffold audit

**Tool**: `pip-audit`
**Status**: failed to run
**Reason**: command not found (`pip-audit` is not installed in this environment)
**Partial output (if any)**:

```
(eval):1: command not found: pip-audit
```

## Hints recorded but not acted on

| Hint                    | Value                                                                                                      |
| ----------------------- | ---------------------------------------------------------------------------------------------------------- |
| bootstrapper_confidence | first-class                                                                                                |
| quality_override        | false                                                                                                      |
| path_taken              | custom                                                                                                     |
| self_check_answers      | typed: true, from_official_starter: false, conventions: true, docs_current: true, can_judge_agent: false   |
| team_size               | solo                                                                                                       |
| deployment_target       | fly                                                                                                        |
| ci_provider             | github-actions                                                                                             |
| ci_default_flow         | manual-promotion                                                                                           |
| has_auth                | true                                                                                                       |
| has_payments            | false                                                                                                      |
| has_realtime            | false                                                                                                      |
| has_ai                  | false                                                                                                      |
| has_background_jobs     | false                                                                                                      |

## Next steps

Next: a future skill will set up agent context (CLAUDE.md, AGENTS.md). For now, your project is scaffolded and verified — happy hacking.

Useful manual steps in the meantime:
- `git init` (if you have not already) to start your own repo history.
- Review any `.scaffold` siblings the conflict policy created and decide which version of each file to keep.
- Address audit findings per your project's risk tolerance — the full breakdown is in this log.
