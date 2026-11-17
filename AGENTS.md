# Repository Guidelines


## Hard Rules

- **Frontend work (anything in `src/compass/page.py`, `i18n.py`, the login page): read `STYLE_GUIDE.md` first**
  and update it when you add a pattern, a token or learn a pitfall. Key rules: DOM calls only (no
  `innerHTML`), no external requests, every UI string in both languages, no controls without a function.

## Project Structure

- `src/compass/`: FastAPI app (`main.py`, `api.py`, `notes.py`, `categories.py`, `transfer.py`, `db.py`,
  `search.py`, `auth.py`), UI in `page.py` and `i18n.py`. Frontend conventions: `@STYLE_GUIDE.md`.
- `tests/`: pytest; `demo/`: importable demo data; `context/`: PRD, roadmap and change plans.

See `@context/foundation/prd.md` for domain rules and `@context/foundation/tech-stack.md` for stack rationale.

## Build & Development Commands

API docs: `http://localhost:8011/docs`.

## Coding Style & Conventions

## Pre-commit Hooks

After cloning, install the hooks once:

```bash
pip install pre-commit
pre-commit install          # file-staged secrets scan on git commit
pre-commit install --hook-type commit-msg   # conventional-commit lint on commit message
```

Hooks defined in `.pre-commit-config.yaml`:

## Commit Guidelines

Conventional Commits format required: `type(scope): subject` — e.g. `fix(pre-commit): restore project-specific hooks`. Allowed types: `feat`, `fix`, `chore`, `docs`, `refactor`. One-line subject under 72 characters. Reference the PRD FR number in the body when implementing a functional requirement (e.g. `Implements FR-009`).
