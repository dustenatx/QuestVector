# QuestVector Backlog

Captured 15 Oct 2026. Work items to plan and discuss before implementation.
Each item notes what is already known from the 15 Oct review.

## 1. Review critical setup from the Gemini → Claude build
Audit the core decisions made across the two AI-directed stages for mistakes
or drift. Known starting points:
- **Two template schemas existed side by side.** The repo's `templates/` held
  the pre-reconciliation schema and failed validation; fixed on
  `fix/ci-and-repo-hygiene`. Check for other leftovers of the old schema
  (`narrative_weighting`, `jd_analysis_rules`) and decide whether the
  backward-compatibility path in `questvector/core/templates.py` is still needed.
- **README contradicts itself.** The banner says the project "has never been
  tested"; the status table says "Implemented, tested, runs today."
- **Vault.** Review key derivation, file permissions, and how the passphrase or
  key is supplied (`questvector/core/vault.py`).
- **LLM data flow.** Confirm exactly what dossier content is sent to remote
  providers and that the user sees it before it leaves the machine.
- **Spec traceability.** Code cites `MASTER_DEVELOPER_SPEC.pdf` section numbers;
  that file isn't in the repo. Decide whether to add it, or re-point citations
  to `docs/QuestVector_Spec.pdf`.

## 2. GitHub configuration, modeled on risk-trainer
Compare against risk-trainer's scanning and repository settings and adopt
what fits a local-only Python app. Candidates: branch protection on `main`,
required status checks, Dependabot (pip and GitHub Actions), CodeQL or
Semgrep, secret scanning with push protection, and pinning actions to commit
SHAs.

## 3. Fix spec Section 10.2
`docs/QuestVector_Spec.pdf` Section 10.2 (repository source layout) likely
still shows the removed `templates/starter/*.yaml` files and
`templates/boilerplate.yaml`. Regenerate the PDF from its source with the
current layout.

## 4. Unit tests: CI and optional-extras failures
- The 142 tests never run in CI; only template validation does. Add a
  `pytest` job (with coverage) on pull requests and pushes to `main`.
- 13 tests in `tests/test_llm.py` fail with `ModuleNotFoundError` unless the
  `[llm]` extra is installed. They should skip cleanly (for example
  `pytest.importorskip`) or CI should install `.[dev,llm]` explicitly.
- Decide how to test the desktop app (`tests/test_desktop_api.py` covers the
  Python bridge only, not the web UI).

## 5. Bring resume lessons from the Applying for Jobs project into export
The job-search project has hard-won rules for ATS-safe resumes that
QuestVector's PDF/DOCX export (`questvector/core/exporter.py`) likely doesn't
follow yet. Evaluate adopting:
- Single column, no tables, text boxes, columns, tab stops, or header/footer
  content.
- Two-line role headers with the employer repeated on every role;
  `Mon YYYY – Mon YYYY` dates.
- Real hyperlinks for email and profile URLs.
- A 20-year date cutoff with a dateless "Earlier Career" line.
- An automated ATS check (an adaptation of `ats_check.py`): extraction across
  three parsers, page count, third-person pronouns, AI-tell phrases, and
  overused words.
- Narrative prompt guardrails: no invented metrics, titles, or technology
  claims, and no pronoun leaks.
Also look for gaps beyond ATS, such as cover-letter output and job-fit reads.

## 6. MCP servers and tooling for code quality and coverage
Add development-time MCP servers as in risk-trainer, for example Playwright
(desktop web UI testing) and Semgrep (static analysis). Also consider:
coverage thresholds, `ruff` linting and formatting, `mypy` type checking,
pre-commit hooks, and `pip-audit` for dependency vulnerabilities. The app
runs locally, but these improve quality without changing that.

## 7. Further topics to discuss
- Release and versioning: tagged releases, a changelog, and how users get
  updates without a hosted service.
- Packaging and install experience across macOS, Windows, and Linux
  (pywebview's platform dependencies; Python 3.12+ requirement).
- Privacy documentation: a short threat model for local data and the vault.
- Accuracy of public claims: the README, spec, and resume wording ("142-test
  automated suite," "proof of concept") should stay consistent as this
  changes.
- Remaining issue templates and the contributing guide, now that CI works.
- Whether the Web Cockpit roadmap stays in the README or moves to its own
  document.
