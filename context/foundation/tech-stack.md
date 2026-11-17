---
starter_id: fastapi
package_manager: uv
project_name: compass
hints:
  language_family: python
  team_size: solo
  deployment_target: docker
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
---

## Why this stack

A solo developer building a small single-user knowledge base in three weeks of after-hours work, with login as the only technology-forcing feature. Custom path: the user already chose a Python backend with a React/Next.js frontend and SQLite, so the recommended web default (Django) was declined. FastAPI clears all four agent-friendly gates (typed with Pydantic, convention-based, popular within Python, well documented) and its bootstrapper confidence is first-class. The registry card covers only the backend half; the Next.js frontend (static export, served by the backend) is added by hand and is not scaffolded by this starter. The app ships as a single Docker image with one process, with a volume for the SQLite data; the image is built locally for now and later published as a GitHub package and pulled from there (no hosting platform). The user's earlier wish to avoid multi-package repositories is in tension with a Python plus Node layout and was accepted knowingly. CI is GitHub Actions with manual promotion after merge. The self-check flagged two gaps (no official template for the combined layout, limited confidence in judging agent output), so project instructions in CLAUDE.md or AGENTS.md should compensate.
