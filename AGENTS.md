# Repository Guidelines


## Hard Rules

## Project Structure


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
