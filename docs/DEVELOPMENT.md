# Development guide

How to set up QuestVector for development, run the checks, and submit a
change. For using QuestVector, see the [README](../README.md); for
contributing a mission template only, see
[CONTRIBUTING_TEMPLATES.md](../CONTRIBUTING_TEMPLATES.md).

## Setup

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/) 0.13.1 or later
([ADR-0013](decisions/0013-python-3-14-uv-lock.md)). On macOS with
Homebrew: `brew install python@3.14 uv`. uv can also download Python 3.14
itself.

```bash
git clone https://github.com/dustenatx/QuestVector.git
cd QuestVector
uv sync --all-extras               # creates .venv from uv.lock
```

`uv sync` installs the exact versions in `uv.lock`, plus the `dev`
dependency group: pytest, mypy, pyflakes, and the type stubs mypy needs.
`--all-extras` adds the three cloud AI provider SDKs (`[llm]`). Without it,
the 13 tests that patch those SDKs skip with the reason shown; install it to
run all 173 that run by default (the live Ollama test is opt-in; see below).
Run commands with `uv run` (for example `uv run qv --version`), or
`source .venv/bin/activate` first. Running the desktop app
(`uv run python -m questvector.desktop.app`) also needs pywebview's platform
dependencies and a display.

### Dependencies and the lock file

`pyproject.toml` holds the version ranges; `uv.lock` pins the exact versions
for every platform. Commit both together. CI runs `uv sync --locked`, which
fails if the lock doesn't match `pyproject.toml`.

```bash
uv add <package>                      # runtime dependency
uv add --optional llm-openai <pkg>    # into an extra
uv add --group dev <package>          # contributor tool
uv lock --upgrade-package <package>   # move one package to its newest allowed version
uv lock --check                       # is the lock current?
```

The lock only takes releases at least 7 days old (`exclude-newer` in
`pyproject.toml`), the same cooldown Dependabot uses. Dependabot opens
weekly pull requests that update `uv.lock`.

## Checks

Run all of these before opening a pull request:

```bash
uv run pytest                                     # 174 tests: 173 run, 1 live test skipped (13 more skip without [llm])
uv run pytest --cov=questvector                   # fails below 90% line coverage
uv run mypy questvector                           # type checks; expect "no issues found"
uv run pyflakes questvector tests                 # lint; expect no output
uv run qv template validate templates/boilerplate.qv-mission.yaml
```

What CI runs (`.github/workflows/`). Every job installs with uv from
`uv.lock` on Python 3.14, on `ubuntu-24.04`:
- **Tests** (`tests.yml`), on every pull request and push to `main`:
  pytest with coverage with all extras (90% floor enforced), pytest without
  the AI extras (proves the skip path), and mypy plus pyflakes.
- **Template validation** (`template-validation.yml`), on every pull
  request and push to `main`.
- **Security** (`security.yml`), on every pull request and push to `main`:
  gitleaks over the git history, Semgrep with the `p/default` rules, and
  pip-audit over every package in `uv.lock`. gitleaks and Semgrep findings
  also appear on the repository's Security tab.
- **CodeQL**, through GitHub's default setup (repository settings, not a
  workflow file).

Results appear in each run's summary on the pull request's Checks tab. All
of these are required checks on `main`
([ADR-0011](decisions/0011-github-security-baseline.md)): a pull request
can't merge until they pass, and it merges by squash only.

The ruleset lives in `.github/rulesets/main.json`. Renaming, adding, or
removing a CI job means editing that file in the same pull request, then
applying it to the live ruleset (the owner runs this; it needs admin
rights):

```bash
gh api repos/dustenatx/QuestVector/rulesets --jq '.[] | select(.name=="main") | .id'
gh api -X PUT repos/dustenatx/QuestVector/rulesets/<id> --input .github/rulesets/main.json
```

When a pull request renames a required check, the old name never reports,
so that pull request can't merge under the old ruleset. The order is:
1. Wait for the pull request's new checks to pass.
2. Apply the pull request's `main.json` to the live ruleset (from the
   branch, for example `git show origin/<branch>:.github/rulesets/main.json
   | gh api -X PUT repos/dustenatx/QuestVector/rulesets/<id> --input -`).
3. Merge the pull request.

Other open pull requests then wait on the new names until rebased.

To run the security scans locally (optional): `semgrep scan --config
p/default --metrics=off`, and the same pip-audit run CI uses:

```bash
uv export --locked --all-extras --all-groups --no-emit-project --no-hashes \
  --format requirements-txt | sed 's/ *;.*//' > audit-requirements.txt
uv run --only-group audit pip-audit --strict --disable-pip --no-deps -r audit-requirements.txt
```
A false positive can be suppressed with an inline
`# nosemgrep: <rule-id>` comment that states the reason.

No test needs a network connection, an API key, or a display. Narrative
generation is tested against simulated providers by default. The one live
test, against a local Ollama server, is opt-in and skipped otherwise (next
section). A live test against a remote provider is still planned (backlog
item 8).

### Live test against a local Ollama

`tests/test_ollama_live.py` runs narrative generation end to end through
QuestVector's Ollama provider, on the synthetic dossier and job description
in `tests/fixtures/ollama_live/`. Nothing leaves the machine. It checks that
a non-empty narrative comes back without an error; it doesn't check
accuracy (backlog item 5). `answer_key.json` in the same folder lists the
allowed facts and the three trap keywords (Datadog, HashiCorp Vault, SOC 2:
in the job description, not the dossier) for scoring output by hand.

1. Install Ollama from [ollama.com](https://ollama.com/download) and start
   it (the app, or `ollama serve`).
2. Pull a model, for example the default, `ollama pull gemma4:12b-it-q4_K_M`
   (about an 8 GB download).
3. Run:

   ```bash
   QV_OLLAMA_LIVE=1 QV_OLLAMA_MODEL=gemma4:12b-it-q4_K_M uv run pytest tests/test_ollama_live.py
   ```

Settings: `QV_OLLAMA_LIVE=1` turns the test on; `QV_OLLAMA_MODEL` (default
`gemma4:12b-it-q4_K_M`), `QV_OLLAMA_HOST` (default `http://localhost:11434`), and
`QV_OLLAMA_TIMEOUT` in seconds (default 300) are optional. With the test
turned on, an unreachable server or a model that isn't pulled fails the
test rather than skipping it.

Model choice: gemma4:12b-it-q4_K_M had the fewest invented facts in 5 runs
on synthetic data with thinking off, 20 Oct 2026 (none, against 3 of 5 for
both llama3.1:8b and qwen3.5:9b-q4_K_M), on Ollama 0.40.6 on a 24 GB Mac, and is the default since 27 Oct 2026.
QuestVector switches thinking off for every Ollama model
([ADR-0012](decisions/0012-ollama-thinking-off.md)).

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
