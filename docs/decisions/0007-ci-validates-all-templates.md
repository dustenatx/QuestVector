# 0007. CI validates every template, not only changed ones

- **Status:** Accepted
- **Date:** 2026-10-15

## Context
The template-validation workflow used `tj-actions/changed-files` to find
changed templates and validated only those. It also set up Node and ran
`npm install`, so it could never install the Python `qv` CLI. The
`tj-actions/changed-files` action family was compromised in a March 2025
supply-chain attack.

## Decision
Install QuestVector with pip on Python 3.12 and validate every `.yaml` and
`.yml` file under `templates/` on each run. Trigger on pull requests and
pushes to `main` that touch templates, the validator
(`questvector/core/templates.py`), or the workflow, plus manual runs.

## Consequences
- No third-party action for change detection; less supply-chain exposure.
- A validator change re-checks every template, catching regressions.
- Run time grows with the number of templates; revisit only if that becomes
  slow.
