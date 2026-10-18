# 0011. GitHub security baseline modeled on risk-trainer

- **Status:** Accepted
- **Date:** 2026-10-18

## Context
`main` had no branch protection, so "never push to main" (CLAUDE.md) was a
convention only. Workflows referenced actions by movable version tags
(`@v4`), which is how the 2025 tj-actions compromise reached other
repositories. Nothing scanned the git history for secrets, ran static
analysis beyond CodeQL, or audited dependencies for known vulnerabilities.

Already in place and kept: CodeQL default setup (weekly and on pull
requests), secret scanning with push protection, Dependabot alerts and
security updates, and a read-only default workflow token.

risk-trainer, the owner's other public repository, has a tested baseline
(backlog item 2). Options considered for the parts that don't carry over:
- **Merge method:** squash-only with linear history (as risk-trainer), or
  keep merge commits. Squash chosen: one commit per pull request on `main`.
- **Dependency audit:** risk-trainer audits a `uv.lock`. QuestVector has
  no lock file; adding one is a packaging change that belongs with
  backlog item 11. Chosen: audit the versions pip installs on each run.
- **AI review workflow:** risk-trainer runs a Claude review on every pull
  request with a stored subscription token. Left out for now.
- **Admin bypass:** risk-trainer's ruleset has no bypass actors. Mirrored:
  no bypass, including for the owner.

## Decision
**In the repository (`.github/`):**
- Every action is pinned to a full commit SHA with a version comment, and
  checkout uses `persist-credentials: false`.
- `security.yml` runs on every pull request and push to `main`:
  - gitleaks 8.30.1 (binary checksum pinned) over the full history.
  - Semgrep 1.179.0 (image pinned by digest) with `p/default`.
  - pip-audit 2.10.1 on a frozen list of every package installed with
    `.[dev,llm]`, except QuestVector itself.
  gitleaks and Semgrep upload SARIF to the Security tab; the upload is
  skipped for fork pull requests, and inline-suppressed Semgrep results are
  dropped first so approved `nosemgrep` lines don't open alerts.
- Template validation runs on every pull request, not only when templates
  change, so it can be a required check.
- `dependabot.yml`: weekly version updates for pip and GitHub Actions,
  minor and patch bumps grouped, majors separate, 7-day cooldown after a
  release.
- `SECURITY.md` points reporters to GitHub private vulnerability reporting.

**In repository settings (applied after the pull request that adds the
checks has merged, since a check must have run before it can be required):**
- A ruleset on `main`, defined in `.github/rulesets/main.json` so changes
  to it are reviewed like code, with no bypass actors: no deletion, no force push,
  linear history, pull request required (0 approvals, squash only, review
  threads resolved), and these required status checks:
  `pytest (full, Python 3.12)`, `pytest (full, Python 3.13)`,
  `pytest (minimal, Python 3.12)`, `mypy and pyflakes`,
  `Validate mission templates`, `gitleaks`, `semgrep`, `pip-audit`. CodeQL
  results also gate merges (errors, and security alerts high or higher).
- Private vulnerability reporting on; head branches deleted after merge.

**Findings from the first scan:** Semgrep flagged the Ollama `urlopen`
call, because urllib also opens `file://` URLs and the host is
user-configurable. The Ollama generator now rejects a host that isn't
`http://` or `https://`, and the call carries a `nosemgrep` with the
reason. Semgrep's Python 3.7 compatibility warning on `importlib.resources`
is suppressed inline, since the project requires Python 3.12.

## Consequences
- Every change to `main` goes through a pull request with all checks green;
  the owner can't skip that, even in an emergency, without first editing
  the ruleset.
- Required check names are tied to job names. Renaming a job, or changing
  the test matrix, without updating the ruleset leaves every pull request
  waiting for a check that never reports. CLAUDE.md requires the job and
  `main.json` to change in the same pull request. GitHub doesn't read that
  file; it is applied with `gh api` (see `docs/DEVELOPMENT.md`), so the
  file and the live ruleset can drift if a change isn't applied.
- With 0 required approvals, GitHub enforces checks but not human review;
  the owner's review remains a practice.
- pip-audit results can change without a code change when a new advisory
  is published or pip resolves a newer version. Revisit with a lock file in
  backlog item 11.
- Dependabot opens more pull requests; grouping and the cooldown limit the
  volume.
