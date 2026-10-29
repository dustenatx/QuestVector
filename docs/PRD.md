# QuestVector — Product Requirements Document

| Field | Value |
|---|---|
| Product | QuestVector: the Python desktop build (`qv` CLI and desktop app), and the planned browser app ([ADR-0016](decisions/0016-browser-app-static-pages.md)) |
| Owner | Dusten Harrison |
| Version | 0.2 — 28 Oct 2026 (adds the browser app); 0.1 — 15 Oct 2026 (first PRD, written after the 1.0.0 build) |
| Status | Draft for owner review |
| Build path | AI-directed. Requirements came from a Google Gemini brainstorming session; Claude built 1.0.0 from them. Changes go through a branch and pull request with CI checks; the owner approves every merge. |
| Cost constraint | $0 beyond the owner's Claude subscription: no paid APIs, no paid hosting (the browser app's static GitHub Pages site is free for a public repository) |
| Related documents | `docs/QuestVector_Spec.pdf` (how 1.0.0 works), `docs/decisions/` (why), `docs/BACKLOG.md` (planned work), `CHANGELOG.md` (what changed) |

This document states what QuestVector must do and why. The system spec
describes how the current build does it; where the two differ, this
document states the intent and the spec is updated to match. Every
requirement is marked **Built** (in 1.0.0 and covered by tests) or
**Planned** (with its backlog item). Anything not written here is out of
scope until the owner adds it.

---

## 1. Summary

QuestVector is a local-first career tool for experienced IT professionals.
The user keeps their career history as three Markdown files: capabilities,
chronology, and quantified impact. QuestVector scores that history against
a job description using a weighted, role-specific mission template; reports
the match score, gaps, and red flags; and compiles a tailored PDF or DOCX
resume bundle. Optionally, the user can ask an AI provider of their choice
to draft a resume summary, including a local model that never leaves the
machine.

It comes in two forms that share one Python core:

- **The desktop app and `qv` CLI** run from a local install (a release wheel
  or a clone). The dossier is plain Markdown in a local workspace folder.
- **The browser app** (planned,
  [ADR-0016](decisions/0016-browser-app-static-pages.md)) is for users who
  can't install software. It's a set of static files on this repository's
  GitHub Pages site, running the same core in Pyodide. The dossier stays in
  the browser, or in a folder the user picks on browsers that allow it.
  There is no backend, no account, and no data collection.

In both, nothing about the user's career data leaves their machine unless
they configure a remote AI provider and explicitly ask for a narrative. The
first browser version has no AI (R28).

## 2. Goals and non-goals

### Goals
- G1. Show the user, before they apply, how well their documented history
  covers a specific job description, and where the gaps and red flags are.
- G2. Keep career data private: stored locally, readable without
  QuestVector, and sent nowhere without an explicit user action.
- G3. Produce resume output an applicant tracking system (ATS) parses
  correctly and a recruiter can read.
- G4. Keep every generated claim traceable to the dossier: no invented
  titles, metrics, dates, or technology claims.
- G5. Work at $0: a local model must be a complete alternative to paid APIs.
  This applies to the desktop app; the browser app has no local model.
- G6. Be explainable: the user can see why a score is what it is.
- G7. Let others extend it: new mission templates and new AI providers
  without changes to core code.
- G8. Be usable by less-technical users with no install and no admin
  rights: the browser app works in current desktop Chrome, Safari and
  Firefox, and in Edge (expected but not yet tested) (§5.9). Mobile browsers aren't a goal until they've been tested.

### Non-goals
- Hosting, accounts, telemetry, or any public distribution channel other
  than release files on this repository's GitHub Releases and the browser
  app's static GitHub Pages site (ADR-0001, narrowed by ADR-0014 and
  ADR-0016). The Pages site serves static files only: no backend and no
  data collection.
- Applying to jobs, scraping job boards, or tracking applications.
- Semantic or embedding-based matching. Keyword matching is a deliberate
  choice for predictability (ADR-0006); revisit only through a new decision.
- Writing the whole resume with AI. AI drafts the summary only; experience
  content comes from the dossier.

## 3. Users and use cases

| User | Use case |
|---|---|
| Experienced IT professional (5–10+ years) | Scores a job description before applying, sees gaps, decides whether to apply |
| Job seeker tailoring an application | Exports a resume bundle matched to one posting, optionally with an AI-drafted summary |
| Privacy-conscious user | Runs everything with a local model; no data leaves the machine |
| Less-technical job seeker (no install or admin rights) | Opens the browser app in a desktop browser, keeps the dossier in the browser or a chosen folder, scores job descriptions and exports a resume bundle (G8) |
| Template contributor | Writes a mission template for their field, validates it locally, and submits a pull request |
| Owner as developer and learner | Extends the tool through AI-directed development and uses it to learn local LLMs, testing, and CI |

## 4. Core concepts

- **Dossier.** Three Markdown files in a workspace: `Capabilities.md`,
  `Chronology.md`, `Impact.md`. The user owns and edits them directly.
- **Workspace.** A local folder created by `qv launch`, holding the dossier,
  templates, exported bundles, and the vault.
- **Mission template.** A YAML file of weighted categories, each with
  keywords, describing what a role type values (ADR-0003). Weights sum to 1.00.
- **G-Force score.** The weighted coverage of a template's categories, as a
  percentage, with gaps, weak categories, red flags, and an alert level
  (ADR-0006).
- **Bundle.** A PDF or DOCX compiled from the dossier, optionally with a match
  summary and an AI-drafted narrative.
- **Vault.** An encrypted local file holding the AI provider choice and keys
  (ADR-0002).
- **Provider.** An AI service that drafts the narrative: Anthropic, OpenAI,
  Gemini (remote), or Ollama (local) (ADR-0004, ADR-0005).

## 5. Functional requirements

Acceptance criteria use EARS-style phrasing.

### 5.1 Workspace and dossier

**R1 — Workspace setup.** **Built.**
- WHEN the user runs `qv launch --dir <path>`, THEN the system SHALL create
  the dossier stub files, `templates/starter/` with the bundled starter
  templates, an empty `templates/community/`, and `bundles/`.
- The system SHALL NOT overwrite any existing file.
- The system SHALL take an advisory lock before writing to a workspace, so
  two processes can't write at once.

**R2 — Dossier parsing.** **Built.**
- The system SHALL parse the three dossier files into structured data and
  keyword sets, and SHALL report a parse error with the file name rather than
  failing silently.

### 5.2 Matching

**R3 — Score a job description.** **Built.**
- WHEN the user runs `qv sync-ast --target <file> --template <id>`, or runs a
  match in the desktop app, THEN the system SHALL show the G-Force score,
  per-category coverage, gaps, weak categories, red flags, and alert level.
- WHERE `--json` is given, the output SHALL be machine-readable.

**R4 — Scoring rules.** **Built.**
- The score SHALL follow the rules in `questvector/core/matcher.py` and spec
  Section 5. The same inputs SHALL always produce the same score.
- A category with nothing relevant in the job description SHALL NOT lower
  the score.

**R5 — Explain the score.** **Planned** (backlog item 10).
- The documentation SHALL include a worked example showing how one job
  description and one dossier produce a given score, so a user can check it
  by hand.

### 5.3 Mission templates

**R6 — Validation.** **Built.**
- WHEN the user runs `qv template validate <path>`, THEN the system SHALL
  report YAML syntax errors, missing required fields, and weights that don't
  sum to 1.00 (±0.005), and SHALL exit non-zero if the template is invalid.
- WHERE `--fix` is given, the system SHALL rescale weights to 1.00 and save
  the file.

**R7 — Contribution path.** **Built** (15 Oct 2026).
- The repository SHALL provide a valid boilerplate at
  `templates/boilerplate.qv-mission.yaml` and a `templates/community/` folder.
- WHEN a pull request or push to `main` touches a template, the validator,
  or the workflow, THEN CI SHALL validate every template under `templates/`
  and fail if any is invalid (ADR-0007, ADR-0008).

### 5.4 Export

**R8 — Bundle export.** **Built.**
- WHEN the user runs `qv export --bundle <name> --format pdf|docx`, THEN the
  system SHALL write the bundle to `bundles/`, including a match summary when
  `--target` and `--template` are given.

**R9 — ATS-safe resume output.** **Planned** (backlog item 5).
- Exported resumes SHALL use a single column, with no tables, text boxes,
  columns, tab stops, or content in page headers and footers.
- Each role SHALL have a title line and a "Company | Mon YYYY – Mon YYYY" line,
  with the employer repeated on every role.
- Email and profile URLs SHALL be real hyperlinks.
- WHERE the user enables it, roles that ended more than 20 years ago SHALL move
  to a dateless "Earlier Career" line.

**R10 — Automated output check.** **Planned** (backlog item 5).
- The system SHALL check an exported DOCX by extracting its text through at
  least two independent parsers, and SHALL report missing contact fields,
  role headers separated from their dates, tables, and page count.

### 5.5 AI narrative

**R11 — Explicit, user-triggered generation.** **Built.**
- The system SHALL generate a narrative only WHEN the user runs
  `qv export --narrative` or presses "Generate Narrative" in the desktop app.
- The system SHALL NOT make any other outbound network call. The browser
  app fetches only its own static files from its own site (R27).

**R12 — Provider choice and extensibility.** **Built.**
- The system SHALL support Anthropic, OpenAI, Gemini, and Ollama through one
  registry. Adding a provider SHALL require changes only in
  `questvector/core/llm.py`.
- WHEN the user configures a provider, THEN the system SHALL show its setup
  link and any caveat before asking for a key.

**R13 — Show what leaves the machine.** **Planned** (backlog item 1).
- WHEN a remote provider is selected, THEN before sending, the system SHALL
  show the user exactly what dossier and job-description text will be sent
  and to which provider, and SHALL send nothing unless the user confirms.

**R14 — Accuracy guardrails.** **Planned** (backlog item 5).
- The narrative prompt SHALL instruct the model to use only facts in the
  supplied dossier text and to add no titles, metrics, dates, employers, or
  technologies.
- The system SHALL flag narrative sentences containing numbers or proper
  nouns that don't appear in the dossier, for the user to review.

**R15 — Live provider testing at no cost.** **Partly built.**
- The test suite SHALL include opt-in live tests, skipped by default, for at
  least one remote provider on a free tier and for a local Ollama model.
- Live tests against remote providers SHALL use synthetic data only.
- Built: the local Ollama live test (`tests/test_ollama_live.py`), on
  synthetic data, skipped unless `QV_OLLAMA_LIVE=1`.
- Planned (backlog item 8): the remote-provider live test.

### 5.6 Vault

**R16 — Encrypted storage.** **Built.**
- The system SHALL store provider settings and keys only in the encrypted
  vault, never in plain-text config files.
- Check: **Built** (backlog item 13). `tests/test_secrets_never_leak.py`
  confirms API keys and the passphrase never appear in command output,
  error messages, logs, exported bundles, or the vault file's bytes.
- A wrong passphrase or tampered file SHALL produce a clear error, never
  garbage output.

**R17 — Stronger key derivation.** **Built** (backlog item 13,
[ADR-0015](decisions/0015-pbkdf2-1m-iterations-vault-v2.md)).
- Key derivation SHALL use PBKDF2-HMAC-SHA256 at no fewer than 600,000
  iterations (OWASP minimum); new vaults use 1,000,000. Vault files record
  and authenticate their key-derivation settings.
- Existing vaults SHALL open and be re-encrypted with the new settings on
  next save, without the user re-entering keys.

### 5.7 Desktop app

**R18 — Safe bridge.** **Built.**
- Every desktop bridge method SHALL return `{"ok": true, "data": ...}` or
  `{"ok": false, "error": "..."}` and SHALL NOT raise to the interface.

**R19 — Interface testing.** **Planned** (backlog items 4, 6).
- Automated browser tests (for example Playwright) SHALL cover each desktop
  tab's main path: open a workspace, run a match, validate a template, export,
  and configure a provider.

### 5.8 Repository and CI

**R20 — Pull request checks.** **Partly built.**
- Built: template validation (R7).
- Planned (backlog items 2, 4, 6): WHEN a pull request is opened or updated,
  THEN CI SHALL run tests with coverage, lint (ruff), type checks (mypy),
  static analysis (Semgrep or CodeQL), secret scanning, and a dependency audit
  (pip-audit).
- Planned: every third-party action SHALL be pinned to a commit SHA, and
  workflows SHALL default to read-only permissions.
- Planned: IF any required check fails, THEN the pull request SHALL be
  blocked from merging into `main`.

**R21 — Records kept current.** **Built** (15 Oct 2026).
- Every merged change to behavior, packaging, CI, or documentation SHALL add a
  `CHANGELOG.md` entry, and every significant design choice SHALL get a record
  in `docs/decisions/`.

### 5.9 Browser app

The browser app follows [ADR-0016](decisions/0016-browser-app-static-pages.md)
and is built under backlog item 16. The figures below come from the
browser/Pyodide spike
([`docs/spikes/2026-10-browser-pyodide.md`](spikes/2026-10-browser-pyodide.md)).

**R22 — Core in a Web Worker.** **Planned** (backlog item 16).
- The browser app SHALL run the unmodified QuestVector Python core in
  Pyodide, inside a Web Worker, so starting Python and running the core
  never freeze the page.
- For the same dossier, job description and template, the browser app SHALL
  give the same scores as the desktop app (R4).

**R23 — Files and browser storage.** **Planned** (backlog item 16).
- WHERE the browser supports the File System Access API (Chrome; Edge
  expected but not yet tested), the app SHALL let the user open a folder and
  read and write the dossier there.
- WHERE it doesn't (Safari, Firefox), the app SHALL let the user upload
  dossier files, keep them in browser-private storage, and download them
  again.
- The app SHALL request persistent storage (`navigator.storage.persist()`).
  It SHALL tell the user plainly when data lives only in the browser, and
  SHALL prompt them to download a backup.
- The dossier SHALL stay plain Markdown and SHALL NOT be encrypted in
  browser storage, as on the desktop (G2).

**R24 — Vault with WebCrypto.** **Planned** (backlog item 16, phase f).
- The browser app SHALL use WebCrypto for vault key derivation
  (PBKDF2-HMAC-SHA256) and encryption (AES-256-GCM). It SHALL use the same
  vault file format as the desktop app (format 2, R17), so one vault file
  works in both.
- The browser vault is built when AI arrives in the browser app (R28), since
  until then it has no keys to hold.

**R25 — Load export libraries on demand.** **Planned** (backlog item 16).
- The libraries needed only for export (reportlab, python-docx, lxml,
  Pillow; about 5.4 MB) SHALL load only when the user first exports.

**R26 — Strict Content Security Policy.** **Planned** (backlog item 16).
- Every page SHALL carry the strict CSP from the spike, plus
  `worker-src 'self'`, in a `<meta>` tag, because GitHub Pages can't set
  headers.
- The CSP SHALL hold with no violations and SHALL NOT allow `'unsafe-eval'`.
- WHEN the app is loaded inside a frame, THEN it SHALL refuse to render.
  This is a guardrail, not a control (ADR-0016).

**R27 — Pinned, self-hosted assets.** **Planned** (backlog item 16).
- Pyodide and every wheel SHALL be served from the app's own site, pinned to
  exact versions, and checked against known hashes when the site is built.
- The app SHALL load no third-party scripts and SHALL send no analytics or
  telemetry.

**R28 — No AI in the first browser version.** **Planned** (backlog item 16,
phase f).
- The first browser version SHALL offer no narrative generation.
- AI comes to the browser app only after live provider testing (backlog
  item 8), through a browser transport added via the provider registry
  (R12).

## 6. Non-functional requirements

| Area | Requirement |
|---|---|
| Privacy | No telemetry, accounts, or backend. The only hosted component is the browser app's static Pages site, which collects no data (ADR-0016, R27). Dossier files stay plain Markdown the user can read and edit without QuestVector. Remote AI calls only on explicit request (R11, R13). |
| Security | Secrets only in the encrypted vault (R16, R17). No secrets in the repository, logs, or bundles. Dependencies audited in CI (R20). |
| Cost | $0: no paid API is required for any feature; Ollama is a complete alternative (G5). |
| Accuracy | Generated text is traceable to the dossier (G4, R14). Public descriptions of the project match what has actually been tested. |
| Portability | Python 3.14 on macOS, Windows, and Linux ([ADR-0013](decisions/0013-python-3-14-uv-lock.md)). The CLI needs no display; the desktop app needs pywebview's platform dependencies. The browser app targets current desktop Chrome, Safari and Firefox, and Edge (expected but not yet tested) (G8); mobile is untested and not a goal yet. |
| Maintainability | Full type hints; mypy and lint clean; Google-style docstrings on public code; one exception hierarchy with no bare `except:`; standard library first. |
| Testability | Every module testable without a network, display, or API key. Coverage target to be set under backlog item 4. |
| Accessibility | Desktop app usable by keyboard with visible focus; color never the only signal of match status. |

## 7. Definition of done for the first full (non-pre-release) release

1. Every requirement marked Planned for backlog items 1, 4, 5, 8, 9, and 13 is
   built, or deferred in writing with its reason.
2. All CI checks green on `main`; required checks enforced by branch
   protection.
3. Narrative generation run end to end with a real local Ollama model and at
   least one free-tier remote provider; results recorded.
4. README, spec, PRD, and `CHANGELOG.md` agree, and "never been tested"
   wording is replaced per backlog item 1's exit condition.
5. The owner has run a full cycle with their own dossier: launch, match,
   export, review the bundle.

## 8. Open questions

- Which free-tier remote provider to use for live tests, and whether its
  terms allow test use (backlog item 8).
- Which local model gives the most accurate summaries on the owner's
  hardware (backlog item 9).
- Whether the legacy template-schema path is still needed (backlog item 1).
- Whether to add `MASTER_DEVELOPER_SPEC.pdf` to the repo, or re-point code
  citations to `docs/QuestVector_Spec.pdf` (backlog item 1).
- Coverage target and which checks are required versus advisory (backlog
  items 2, 4).
- Whether ATS rules (R9) should be fixed defaults or template-controlled
  settings.

## 9. Out of scope (candidates for later)

Cover-letter generation; job-fit reads beyond the G-Force
score; semantic matching; importing resumes or LinkedIn profiles into the
dossier; application tracking; a packaged installer.
