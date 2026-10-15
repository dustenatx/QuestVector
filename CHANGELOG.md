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

### Added
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
- mypy, pyflakes, and the type stubs mypy needs (`types-PyYAML`, `types-reportlab`) in the `[dev]` extra, so the spec's "mypy clean" claim can be reproduced.

### Changed
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
- `tj-actions/changed-files` dependency from the workflow.
- Seven stale starter templates in `templates/starter/` and
  `templates/boilerplate.yaml`, which used the pre-reconciliation schema and
  failed validation. The bundled copies in `questvector/data/starter_templates/`
  are the only source. ([ADR-0009](docs/decisions/0009-bundled-starter-templates-only.md))
- Committed `.DS_Store` files.

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

[Unreleased]: https://github.com/dustenatx/QuestVector/compare/70f380d...HEAD
[1.0.0]: https://github.com/dustenatx/QuestVector/commit/70f380d
