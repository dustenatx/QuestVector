# 0010. `__version__` is the single source of the version

- **Status:** Accepted
- **Date:** 2026-09-15

## Context
The version string was duplicated in `pyproject.toml` and the package, so
the two could drift.

## Decision
Define the version once, as `__version__` in `questvector/__init__.py`.
`pyproject.toml` reads it dynamically, and `qv --version` reports it.

## Consequences
- Packaging metadata and the CLI always agree.
- A release bumps one line, alongside the `CHANGELOG.md` entry.
