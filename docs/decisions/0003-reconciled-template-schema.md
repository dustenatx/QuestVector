# 0003. One reconciled mission-template schema

- **Status:** Accepted
- **Date:** 2026-09-09

## Context
Two schemas existed. The build's own design used weighted `categories`, each
with keywords. `CONTRIBUTING_TEMPLATES.md`, written separately during the
design stage, used a fixed `narrative_weighting` split (capabilities,
chronology, impact stories) plus `jd_analysis_rules`. The spec published
neither.

## Decision
Merge them into one schema: keep weighted `categories` (more expressive for
JD matching), and adopt `schema_version`, `mission_id`, `metadata`,
`jd_analysis`, and `output_formatting` from the contributing guide. Only
`name` and `weight` are required per category; weights must sum to 1.00.
A flat `id`/`title` at the root is still accepted for backward
compatibility. The full schema is in `questvector/core/templates.py`.

## Consequences
- One validator, one contributing guide, one boilerplate.
- Old-schema files fail validation. The stale copies in the repo's
  `templates/` folder were removed on 15 Oct 2026 (see 0009).
- **Revisit:** whether the backward-compatibility path is still needed
  (backlog item 1).
