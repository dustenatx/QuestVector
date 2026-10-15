# 0008. CI reports results in the run summary, not a PR comment

- **Status:** Accepted
- **Date:** 2026-10-15

## Context
The workflow posted the same canned PR comment on every run, pass or fail.
The comment claimed checks the validator doesn't perform ("narrative weight
balance," "2026 keyword density"), needed write access to pull requests, and
cannot post on pull requests from forks, which receive a read-only token.

## Decision
Write real per-file results (template, valid or invalid, validator output)
to the Actions run summary, annotate failing files, and fail the job when
any template is invalid. The workflow token is read-only
(`permissions: contents: read`).

## Consequences
- Feedback reflects what was actually checked.
- Works for contributors on forks.
- Results are one click away on the Checks tab rather than inline on the
  pull request.
