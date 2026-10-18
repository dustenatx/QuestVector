# QuestVector: notes for Claude

Local-first career tool: a `qv` CLI and a pywebview desktop app over one
Python core. Read these before changing anything:

- `docs/BACKLOG.md`: planned work, by item number. Work one item at a time.
- `docs/PRD.md`: requirements, each marked Built or Planned.
- `docs/decisions/`: why things are built the way they are. Don't reverse a
  decision without a new record that supersedes it.
- `docs/DEVELOPMENT.md`: setup, checks, layout, and conventions.

## Rules

- **Local-only (ADR-0001).** No hosting, telemetry, or new outbound network
  calls. The only network path is user-triggered narrative generation
  through a remote AI provider. Backlog item 14 discusses hosting; nothing
  is decided.
- **No secrets or real career data in the repo or tests.** Tests use
  synthetic data and simulated providers. No test may need a network
  connection, an API key, or a display.
- **Work on a branch and open a pull request to `main`.** The owner reviews
  and merges every change. Never push to `main` directly.
- **Before every commit**, run and pass: `pytest`, `mypy questvector`,
  `pyflakes questvector tests`. CI runs the same checks.
- **Record every change** under `[Unreleased]` in `CHANGELOG.md`; add a
  record in `docs/decisions/` for any significant design choice; update the
  PRD when a requirement changes; mark backlog items done when finished.
- **Accuracy of public claims.** The README banner says the project has
  never been tested against a live AI provider. Change it only per the exit
  condition in backlog item 1.

## Code conventions

Python 3.12+, full type hints, Google-style docstrings, standard library
first. Raise a `QuestVectorError` subclass, never a bare `except:`. Desktop
bridge methods return `{"ok": ..., "data"|"error": ...}` and never raise. Add
AI providers only through the registry in `questvector/core/llm.py`.

## The owner

Dusten directs the work and reviews it; he doesn't write the code by hand.
Explain changes in plain language, flag risks before acting, and ask before
anything hard to undo.
