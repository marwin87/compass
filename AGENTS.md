# Repository Guidelines


## Hard Rules

- **Frontend work (anything in `src/compass/ui/`: pages, scripts, styles, translations, the login page): read `docs/STYLE_GUIDE.md` first**
  and update it when you add a pattern, a token or learn a pitfall. Key rules: DOM calls only (no
  `innerHTML`), no external requests, every UI string in both languages, no controls without a function.

## Project Structure

- `src/compass/`: the backend (FastAPI app). Shell: `main.py`, `auth.py`, `config.py`, `db.py`, `settings.py`,
  `about.py`, `search.py` (text folding and fuzzy matching, used by `db.py` and the domain). `routes/`: one module per
  HTTP resource; `api.py` holds the limits and error maps the routes share. `notes/`: the notes domain (`__init__.py`
  is the notes themselves; `categories.py`, `tags.py`, `summaries.py`, `transfer.py` for export/import files).
  `ai/`: everything that calls a model (`__init__.py` is the client; `chunks.py` the vector index, `retrieval.py`
  the excerpts for a question, `chat.py` the saved conversations). `importing/`: file import (`importer.py`
  with the `docx.py`, `pdf.py` and `textfile.py` readers).
- `src/compass/ui/`: everything the browser receives: pages (`page.py`, `settings_page.py`, `login.py`), shared
  script (`core.py`), the note reader and editor (`reader.py`, `editor.py`) and translations (`i18n.py`). The backend
  never builds HTML; frontend conventions: `@docs/STYLE_GUIDE.md`.
- `web/assets/`: the CSS, JS and HTML of every page (real files, `src/compass/ui/*.py`
  assemble them; a checkout finds them by itself, the Docker image sets `COMPASS_ASSETS_DIR`).
- `tests/`: pytest, laid out like `src/compass/`: backend tests in `tests/notes/`, `tests/ai/` and
  `tests/importing/` (one file per area; app-level ones in `tests/`), UI tests in `tests/ui/` (see `docs/STYLE_GUIDE.md`); `demo/`: importable demo data; `context/`: PRD, roadmap and change plans.

See `@context/foundation/prd.md` for domain rules and `@context/foundation/tech-stack.md` for stack rationale.

## Build & Development Commands

API docs: `http://localhost:8011/docs`.

Browser (e2e) tests are opt-in and local only: `uv run pytest -m e2e` (first `uv run playwright install chromium`); a plain `uv run pytest` and CI skip them. Rules for writing them: `docs/STYLE_GUIDE.md` section 12.

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
