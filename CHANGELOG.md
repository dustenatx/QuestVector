# Changelog

All notable changes to QuestVector are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/). The version number lives in one
place, `questvector/__init__.py` (`__version__`).

**Keeping it current:** every pull request that changes behavior, packaging,
CI, or documentation adds a line under `[Unreleased]`. On release, rename
`[Unreleased]` to the new version and date, bump `__version__` to match, and
start a fresh `[Unreleased]` section. Significant design choices also get a
record in [`docs/decisions/`](docs/decisions/).

## [Unreleased]

## [1.1.0] - 2026-10-28

The first version published as release files: a pre-release on [GitHub Releases](https://github.com/dustenatx/QuestVector/releases). Installing it needs Python 3.14 (see Removed).

### Added
- `Release` GitHub Actions workflow (`.github/workflows/release.yml`), run only when a `v*` tag is pushed: it tests the tagged commit, checks it is on `main` and that the tag matches `__version__`, builds the wheel and sdist, writes `SHA256SUMS`, attests build provenance with `actions/attest` v4.2.2, and publishes a pre-release with this changelog section as its notes. The release is created as a draft and published only as the last step. ([ADR-0014](docs/decisions/0014-github-releases.md))
- `.github/rulesets/tags.json`: a tag ruleset under which only the repository admin can create, move, or delete `v*` tags (applied by the owner after merge).
- `tests/test_workflows.py`: every workflow pins its actions to a commit SHA with a version comment and checks out without persisting credentials; `release.yml` keeps its tag-only trigger, its permissions, and its draft-then-publish order.
- README "Install from a release" and "Upgrade" instructions, with checksum and attestation checks; `docs/DEVELOPMENT.md` release steps for the owner.
- Opt-in live test of narrative generation against a local Ollama server (`tests/test_ollama_live.py`, on when `QV_OLLAMA_LIVE=1`), with a synthetic dossier, job description, and answer key in `tests/fixtures/ollama_live/`, fixture checks that always run, and a how-to in `docs/DEVELOPMENT.md`.
- `qv vault set-key --timeout SECONDS`: how long to wait for a local Ollama response (default 300 seconds, up from a fixed 120).
- `Security` GitHub Actions workflow: gitleaks (git history), Semgrep (static analysis), and pip-audit (dependency vulnerabilities) on every pull request and push to `main`; gitleaks and Semgrep results also go to the Security tab. ([ADR-0011](docs/decisions/0011-github-security-baseline.md))
- `.github/dependabot.yml`: weekly version updates for pip and GitHub Actions, with a 7-day cooldown.
- `SECURITY.md`: how to report a vulnerability privately.
- `.github/rulesets/main.json`: the `main` branch ruleset (squash-only pull requests, required checks, no bypass), kept in the repo so changes are reviewed, and matching the live ruleset field for field, including the defaults GitHub fills in; and a `CLAUDE.md` rule that a CI job can't be renamed without updating it in the same pull request.
- `Tests` GitHub Actions workflow: pytest with coverage on Python 3.12 and 3.13, a run without the AI extras, and mypy plus pyflakes, on every pull request and push to `main`.
- 90% line-coverage floor in `pyproject.toml` (measured 95%).
- `CLAUDE.md` with project rules for AI-assisted development.
- `.gitignore` for Python caches, build output, virtual environments, and OS files.
- `templates/boilerplate.qv-mission.yaml` in the current schema, at the path
  `CONTRIBUTING_TEMPLATES.md` already referenced.
- `templates/community/README.md` explaining where contributed templates go.
- README "Documentation" section pointing to `docs/QuestVector_Spec.pdf` and
  the video overview.
- `docs/BACKLOG.md` with planned work from the 15 Oct 2026 review.
- This changelog and the decisions log in `docs/decisions/`.
- `docs/PRD.md`, the first product requirements document (draft 0.1).
- `docs/DEVELOPMENT.md`: developer setup, checks, conventions, and the release steps.
- README "Fill in your dossier first" section explaining the dossier format, and a documentation index.
- mypy, pyflakes, and the type stubs mypy needs (`types-PyYAML`, `types-reportlab`) in the dev tools (now the `dev` dependency group), so the spec's "mypy clean" claim can be reproduced.

### Changed
- Distribution: ADR-0001 is narrowed by [ADR-0014](docs/decisions/0014-github-releases.md) so CI may publish release files to GitHub Releases; the app still makes no new network calls, and there is no PyPI package, hosting, or telemetry. The README distribution policy and the PRD non-goal say the same, and the PRD's definition of done now applies to the first full (non-pre-release) release instead of 1.1.0.
- The build backend is pinned to `setuptools==84.2.1` (was `>=68.0`), so release builds don't pick up the newest setuptools of the day; the license metadata uses the SPDX form (`license = "MIT"`, `license-files`) that setuptools now requires.
- `CLAUDE.md`: the CI-job rule covers jobs that run on pull requests (tag-only release jobs aren't required checks), and only the owner creates release tags.
- Python 3.14 only (`requires-python >=3.14`, `.python-version`), with uv for contributors and a committed `uv.lock` covering every platform, extra, and group. The lock only takes releases at least 7 days old (`exclude-newer`), matching Dependabot's cooldown. Users can still install with plain pip on Python 3.14. ([ADR-0013](docs/decisions/0013-python-3-14-uv-lock.md))
- CI moved to uv: `astral-sh/setup-uv` v10.3.0 (pinned to a commit SHA, uv 0.13.1) and `uv sync --locked` in every job. Tests run on Python 3.14 only, full and minimal; the required checks are now `pytest (full, Python 3.14)` and `pytest (minimal, Python 3.14)` (`.github/rulesets/main.json` updated). The test and template-validation jobs run on `ubuntu-24.04` instead of `ubuntu-latest`.
- pip-audit audits every package in `uv.lock` (all extras and groups, including macOS-only packages) instead of what one pip install resolves, and pip-audit itself is locked in an `audit` dependency group.
- Dependabot updates Python dependencies through its `uv` ecosystem, so its pull requests update `uv.lock`.
- The dev tools moved from the `[dev]` extra to a `dev` dependency group, which `uv sync` installs by default.
- The default Ollama model is now `gemma4:12b-it-q4_K_M` instead of `llama3.1`: in [ADR-0012](docs/decisions/0012-ollama-thinking-off.md)'s comparison it invented facts in 0 of 5 runs against 3 of 5 for llama3.1:8b, and the owner's real-dossier run on 27 Oct 2026 backed the choice. It is an 8 GB download instead of 4.9 GB; anyone relying on the old default should run `ollama pull gemma4:12b-it-q4_K_M` or set `--model llama3.1`.
- Backlog item 9 lists three follow-ups from the PR #7 review: a connection reset mid-response escapes as a raw error, `qv vault set-key` resets the timeout when `--timeout` is omitted, and the desktop prompt omits the template's tone.
- Ollama requests switch thinking off (`"think": false`), so thinking models such as qwen3.5 and gemma4 answer within the 600-token limit instead of spending it all on hidden reasoning. ([ADR-0012](docs/decisions/0012-ollama-thinking-off.md))
- Backlog item 1 now records that negative statements in a dossier ("no hands-on Kubernetes") count as keyword matches, and that role titles in `##` headings may not count toward matching ("manager" reported as a gap under "Engineering Manager" headings).
- Every GitHub Action is pinned to a commit SHA (checkout v7.0.1, setup-python v7.0.0), and checkout no longer keeps the token in the working copy.
- Template validation runs on every pull request, so it can be a required check.
- The Ollama generator rejects a host that isn't an `http://` or `https://` URL, instead of passing it to urllib, which also opens `file://` URLs.
- The 13 tests that patch a cloud AI SDK now skip, with the install command as the reason, when that SDK isn't installed, instead of failing.
- Template-validation workflow rewritten for the Python build: installs with
  pip on Python 3.12 and validates every template under `templates/` with
  `qv template validate`. It previously set up Node and ran `npm install`, so
  it could not install the CLI. ([ADR-0007](docs/decisions/0007-ci-validates-all-templates.md))
- Workflow feedback moved from a canned PR comment to real per-file results
  in the Actions run summary; the workflow token is now read-only and the
  check works on pull requests from forks.
  ([ADR-0008](docs/decisions/0008-ci-results-in-run-summary.md))
- README tagline no longer promises application tracking, which doesn't exist; the status table now says testing used simulated AI providers.
- Contributing guide and issue templates no longer refer to the unbuilt Web Cockpit as usable.
- README clarifies that `MASTER_DEVELOPER_SPEC.pdf`, cited by the code's
  "Spec reference" notes, is the original design spec and is not in the repo.

### Removed
- Support for Python 3.12 and 3.13: 1.1.0 installs only on Python 3.14. Anyone upgrading from 1.0.0 on an older Python needs a new 3.14 virtual environment.
- The `[dev]` extra: `pip install -e ".[dev]"` no longer installs the test tools; contributors use `uv sync` (see `docs/DEVELOPMENT.md`).
- `tj-actions/changed-files` dependency from the workflow.
- Seven stale starter templates in `templates/starter/` and
  `templates/boilerplate.yaml`, which used the pre-reconciliation schema and
  failed validation. The bundled copies in `questvector/data/starter_templates/`
  are the only source. ([ADR-0009](docs/decisions/0009-bundled-starter-templates-only.md))
- Committed `.DS_Store` files.

### Fixed
- A slow Ollama response raised a raw `TimeoutError`, which escaped the desktop app's narrative bridge; it now raises `LLMError` with the time limit and how to raise it.
- A model that isn't downloaded was reported as "Could not reach the local Ollama server -- is it running?"; it now says the model isn't downloaded and to run `ollama pull`. Other HTTP errors from Ollama now include Ollama's own message.
- An empty Ollama answer always asked "has the model been pulled?"; running out of tokens, including on hidden reasoning, now gets its own message.

## [1.0.0] - 2026-09-15

### Added
- Narrative generation through four interchangeable providers: Anthropic,
  OpenAI, Google Gemini, and a local Ollama server, behind one data-driven
  provider registry. ([ADR-0004](docs/decisions/0004-data-driven-llm-provider-registry.md),
  [ADR-0005](docs/decisions/0005-ollama-over-plain-http.md))
- `qv vault set-key` options `--provider`, `--model`, and `--host`, printing each
  provider's key-setup link before prompting.
- Desktop provider picker in the Vault panel.
- `qv --version`.
- Per-provider key storage in the vault, with automatic migration of
  single-key vault files.
- `docs/QuestVector_Spec.pdf`, the system specification for the Python build.
- Video overview, `docs/QuestVector - The AI Capability Ladder.mp4`.
- Tests expanded from 108 to 142, covering every provider, the vault
  migration, and the new CLI flags.

### Changed
- `questvector.__version__` is the single source of truth for the version;
  `pyproject.toml` reads it dynamically. ([ADR-0010](docs/decisions/0010-single-source-version.md))
- Package moved under `questvector/`; CLI installed as the `qv` entry point.
- Documentation updated to the local-only distribution policy, replacing the
  original spec's "Zero-Cloud" framing. ([ADR-0001](docs/decisions/0001-local-only-distribution.md))
- README states the project is untested: narrative generation has not run
  against a live provider.

### Fixed
- LICENSE copyright holder and a "(a)" to "(c)" typo.
- A type error in the PDF exporter (`list[object]` to `list[Flowable]`).

## Pre-release history

### 2026-09-09
- First Python build: `qv` CLI (`launch`, `sync-ast`, `export`,
  `template validate`, `vault set-key`), the matching engine and G-Force
  score, the reconciled mission-template schema, seven bundled starter
  templates, the encrypted local vault, PDF and DOCX export, the pywebview
  desktop app, Anthropic narrative generation, and 108 tests.
  ([ADR-0002](docs/decisions/0002-aes-256-gcm-local-vault.md),
  [ADR-0003](docs/decisions/0003-reconciled-template-schema.md),
  [ADR-0006](docs/decisions/0006-independent-g-force-formula.md))
- README note that the project is pre-beta.

### 2026-09-04
- Repository created with the design-stage configuration: issue templates,
  the template-validation workflow, `CONTRIBUTING_TEMPLATES.md`, the MIT
  license, README, and starter templates. Files moved to the repository root.
- `tj-actions/changed-files` updated to v47 (Dependabot pull request #1 and a
  follow-up commit).

[Unreleased]: https://github.com/dustenatx/QuestVector/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/dustenatx/QuestVector/compare/70f380d...v1.1.0
[1.0.0]: https://github.com/dustenatx/QuestVector/commit/70f380d
