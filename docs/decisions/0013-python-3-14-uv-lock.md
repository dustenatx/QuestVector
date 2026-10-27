# 0013. Python 3.14 only, managed with uv and a committed lock file

- **Status:** Accepted
- **Date:** 2026-10-27

## Context
QuestVector supported Python 3.12 and later, and was installed with pip from
the open version ranges in `pyproject.toml`. CI tested 3.12 and 3.13. With no
lock file, two installs a day apart could get different versions, and
pip-audit checked whatever pip resolved on the day it ran (ADR-0011 deferred
the lock to backlog item 11). On 23 Oct 2026 the owner adopted the
engineering baseline already used by risk-trainer: Python 3.14 only, uv, a
committed `uv.lock`, and `.python-version` set to 3.14.

Before deciding, every dependency, extra, and dev tool was resolved for
Python 3.14 and its files checked on PyPI (27 Oct 2026): all publish a 3.14
wheel for macOS arm64 and Linux x86_64 (and Windows), including
cryptography, PyYAML, lxml, pillow, and the pyobjc packages pywebview needs
on macOS. The one exception is `proxy-tools`, a pywebview dependency that
has only ever shipped a pure-Python source package; it builds from source
on every Python version, as it already did on 3.12.

Options considered:
- **pip with a pip-tools lock (`requirements.txt`).** Keeps pip, but needs a
  separate lock per extra combination and per platform, and doesn't match
  risk-trainer.
- **uv, with the dev tools left as an extra.** Works, but `[dev]` would stay
  a user-visible install option.
- **uv, with dev tools in dependency groups (PEP 735).** Chosen. The AI SDKs
  stay as extras, because they are real user install choices and the error
  messages in `questvector/core/llm.py` name them.

## Decision
- `requires-python = ">=3.14"`; `.python-version` is `3.14`.
- uv is the contributor tool. `uv.lock` is committed and covers every
  platform, extra, and group. `[tool.uv] required-version` is `>=0.13.1`,
  the version CI pins.
- The `dev` extra becomes a `dev` dependency group (installed by default by
  `uv sync`). A new `audit` group holds pip-audit, so its version is locked
  too.
- `[tool.uv] exclude-newer = "7 days"`: the lock only takes releases at
  least a week old, the same cooldown Dependabot uses (ADR-0011).
- Users can still install with plain pip on Python 3.14; uv is for
  contributors. GitHub Releases are expected to ship wheels later.
- CI uses `astral-sh/setup-uv` (pinned to a commit SHA) and
  `uv sync --locked`, so a run fails if the lock is out of date. The test
  matrix is Python 3.14 only, full (all extras) and minimal (no AI SDKs).
  Every job runs on `ubuntu-24.04` instead of `ubuntu-latest`.
- pip-audit audits the lock: `uv export` lists every locked package (all
  extras, all groups, platform markers stripped so macOS-only packages are
  included), and pip-audit checks that list.
- Dependabot's Python ecosystem changes from `pip` to `uv`, so its pull
  requests update `uv.lock`.
- Required checks change from `pytest (full, Python 3.12)`,
  `pytest (full, Python 3.13)`, and `pytest (minimal, Python 3.12)` to
  `pytest (full, Python 3.14)` and `pytest (minimal, Python 3.14)`. The
  other required checks keep their names.

This supersedes ADR-0011's choice to audit the versions pip installs on each
run, and its list of pytest check names. The rest of ADR-0011 stands.

## Consequences
- Every install, local or CI, gets the same versions until the lock is
  deliberately changed (`uv lock --upgrade-package <name>`, or a Dependabot
  pull request).
- pip-audit results now change only when the lock changes or a new advisory
  is published against a locked version.
- Anyone on Python 3.12 or 3.13 must move to 3.14. Contributors need uv.
- A dependency added to `pyproject.toml` without re-running `uv lock` fails
  CI, by design.
- The 7-day cooldown means a security fix released today can't be locked
  until next week, unless the cooldown is overridden for that package
  (`[tool.uv] exclude-newer-package`). Revisit if that happens.
- A Dependabot pull request built with the old check names will wait on
  them until it's rebased onto `main` after this change merges.
