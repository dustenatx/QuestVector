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
the 16 tests that patch those SDKs skip with the reason shown; install it to
run all 240 that run by default (the live Ollama test is opt-in; see below).
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

The build backend is outside the lock: `[build-system] requires` pins an
exact setuptools version, so release builds are reproducible
([ADR-0014](decisions/0014-github-releases.md)). Dependabot's uv ecosystem
reads `build-system.requires`, so it is expected to propose setuptools bumps
with the same 7-day cooldown; confirm that on its first cycle after
1.1.0. To bump by hand, pick a release at least 7 days old from
[PyPI's release history](https://pypi.org/project/setuptools/#history),
change the pin, and check `uv build` still succeeds with no warnings.

## Checks

Run all of these before opening a pull request:

```bash
uv run pytest                                     # 241 tests: 240 run, 1 live test skipped (16 more skip without [llm])
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
- **Release** (`release.yml`), only when a `v*` tag is pushed; never on a
  pull request. See [Releasing](#releasing).

Results appear in each run's summary on the pull request's Checks tab. All
of these except Release are required checks on `main`
([ADR-0011](decisions/0011-github-security-baseline.md)): a pull request
can't merge until they pass, and it merges by squash only.

`tests/test_workflows.py` checks every workflow pins its actions to a
commit SHA with a version comment and checks out with
`persist-credentials: false`, and that `release.yml` keeps its tag-only
trigger, permissions, and draft-then-publish order.

The ruleset lives in `.github/rulesets/main.json`. Renaming, adding, or
removing a CI job that runs on pull requests means editing that file in the
same pull request, then
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

The vault's key derivation takes about 150 ms at its shipped 1,000,000
iterations, so an autouse fixture in `tests/conftest.py` (`fast_kdf`)
lowers the iteration count and the read minimum to 1,000 for every test.
The shipped values in `questvector/core/vault.py` don't change; mark a
test `@pytest.mark.real_kdf` to run it against them (the settings checks,
one real round trip, the range checks, and the format 1 fixtures in
`tests/fixtures/vault/` do). `tests/test_secrets_never_leak.py` checks that
API keys and the passphrase never reach output, errors, logs, bundles, or
the vault file; its markers are plain words, so secret scanners don't flag
them. Keep any new synthetic secrets in that style, with no real provider
prefix.

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

Pushing a `v*` tag runs `.github/workflows/release.yml`, which tests the
tagged commit, builds the wheel and sdist, attests them, and publishes a
pre-release on GitHub Releases
([ADR-0014](decisions/0014-github-releases.md)). Only the owner tags; the
tag ruleset lets only the repository admin create, move, or delete `v*`
tags.

**Once, before the first release** (owner, admin rights):
- Turn on immutable releases: Settings → General → Releases.
- Apply the tag ruleset. The first time, create it; afterwards, update it
  by id:

  ```bash
  gh api -X POST repos/dustenatx/QuestVector/rulesets --input .github/rulesets/tags.json
  gh api repos/dustenatx/QuestVector/rulesets --jq '.[] | select(.name=="release-tags") | .id'
  gh api -X PUT repos/dustenatx/QuestVector/rulesets/<id> --input .github/rulesets/tags.json
  ```

**Each release:**
1. On a branch: in `CHANGELOG.md`, rename `[Unreleased]` to
   `## [X.Y.Z] - YYYY-MM-DD`, start a new empty `[Unreleased]` above it, and
   update the compare links at the bottom. Bump `__version__` in
   `questvector/__init__.py` to `X.Y.Z` (`pyproject.toml` reads it). Open a
   pull request and merge it.
2. Tag the merged commit on `main` and push the tag:

   ```bash
   git switch main && git pull
   git tag -a vX.Y.Z -m "QuestVector X.Y.Z"
   git push origin vX.Y.Z
   ```
3. Watch the run: `gh run list --workflow release.yml`, then
   `gh run watch <run-id>`. It fails if the commit isn't on `main`, a check
   fails, the tag doesn't equal `__version__`, or `CHANGELOG.md` has no
   section for the version.
4. Check the result: `gh release view vX.Y.Z` should show a pre-release (not
   a draft) with three files. Download them and verify:

   ```bash
   gh release download vX.Y.Z --dir /tmp/qv-X.Y.Z && cd /tmp/qv-X.Y.Z
   shasum -a 256 -c SHA256SUMS
   gh attestation verify questvector-X.Y.Z-py3-none-any.whl --repo dustenatx/QuestVector
   gh attestation verify questvector-X.Y.Z.tar.gz --repo dustenatx/QuestVector
   ```

**If the run fails:**
- Before the publish step, nothing is public. Delete the draft if one was
  created (`gh release delete vX.Y.Z --yes`) and the tag
  (`git push --delete origin vX.Y.Z`, then `git tag -d vX.Y.Z`), fix the
  problem on a branch, merge, and tag again.
- After publishing, the release can't be changed. Fix forward with a new
  patch version.
