# Development guide

How to set up QuestVector for development, run the checks, and submit a
change. For using QuestVector, see the [README](../README.md); for
contributing a mission template only, see
[CONTRIBUTING_TEMPLATES.md](../CONTRIBUTING_TEMPLATES.md).

## Setup

Requires Python 3.12 or later.

```bash
git clone https://github.com/dustenatx/QuestVector.git
cd QuestVector
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev,llm]"
```

`[dev]` installs pytest, mypy, pyflakes, and the type stubs mypy needs.
`[llm]` installs the three cloud AI provider SDKs. Without it, the 13 tests
that patch those SDKs skip with the reason shown; install it to run all 142. Running the desktop app (`python -m questvector.desktop.app`) also
needs pywebview's platform dependencies and a display.

## Checks

Run all of these before opening a pull request:

```bash
pytest                                            # 142 tests (129 + 13 skipped without [llm])
pytest --cov=questvector                          # fails below 90% line coverage
mypy questvector                                  # type checks; expect "no issues found"
pyflakes questvector tests                        # lint; expect no output
qv template validate templates/boilerplate.qv-mission.yaml
```

What CI runs (`.github/workflows/`):
- **Tests** (`tests.yml`), on every pull request and push to `main`:
  pytest with coverage on Python 3.12 and 3.13 with all extras (90% floor
  enforced), pytest on Python 3.12 without the AI extras (proves the skip
  path), and mypy plus pyflakes.
- **Template validation** (`template-validation.yml`), when templates, the
  validator, or that workflow change.

Results appear in each run's summary on the pull request's Checks tab.

No test needs a network connection, an API key, or a display. Narrative
generation is tested against simulated providers, not live ones (backlog
items 8 and 9).

## Project layout

```
questvector/
  cli.py                 qv command-line interface (argparse)
  config.py              constants: file names, thresholds, stopwords
  exceptions.py          QuestVectorError hierarchy
  core/
    markdown_parser.py   dossier parsing and tokenizing
    matcher.py           G-Force scoring (the only place scoring logic lives)
    templates.py         mission template loading, validation, --fix
    exporter.py          PDF and DOCX bundles
    vault.py             encrypted local vault
    workspace.py         workspace setup and file locking
    llm.py               AI provider registry and narrative generation
  data/starter_templates/  the seven bundled mission templates
  desktop/               pywebview app: app.py (Python bridge), web/ (HTML/JS/CSS)
templates/               contributor boilerplate and community/ templates
tests/                   pytest suite, roughly one file per module
docs/                    PRD, spec, decisions log, backlog, this guide
```

Design reasoning for these choices is in [`decisions/`](decisions/).

## Conventions

- **Code:** full type hints with `from __future__ import annotations`;
  Google-style docstrings on public modules, classes, and functions; raise
  a `QuestVectorError` subclass, never a bare `except:`; standard library
  first, third-party only where it has no equivalent.
- **Desktop bridge:** every `Api` method returns `{"ok": true, "data": ...}`
  or `{"ok": false, "error": "..."}` and never raises to the interface.
- **AI providers:** add one through the registry in `questvector/core/llm.py`
  (a generator class, a factory function, and a registry entry); see that
  module's docstring.

## Submitting a change

1. Create a branch from `main`.
2. Make the change and run the checks above.
3. Add a line under `[Unreleased]` in [`CHANGELOG.md`](../CHANGELOG.md) if the
   change affects behavior, packaging, CI, or documentation.
4. For a significant design choice, add a record in
   [`decisions/`](decisions/) from `0000-template.md`, and list it in that
   folder's README.
5. If the change adds or alters a requirement, update [`PRD.md`](PRD.md).
6. Open a pull request to `main`.

## Releasing

1. Bump `__version__` in `questvector/__init__.py`; `pyproject.toml` reads it.
2. In `CHANGELOG.md`, rename `[Unreleased]` to the new version and date, and
   start a new `[Unreleased]` section.
3. Merge to `main`. There is no publishing step: users update with
   `git pull` (see [ADR-0001](decisions/0001-local-only-distribution.md)).
