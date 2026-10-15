# 0009. Bundled package templates are the only starter source

- **Status:** Accepted
- **Date:** 2026-10-15

## Context
Starter templates existed in two places: `questvector/data/starter_templates/`
(the package data, in the current schema, used at runtime) and the repo's
`templates/starter/` (the old schema with placeholder keywords, never read by
the app). The repo copies failed validation and would have failed CI.

## Decision
Keep the bundled package copies as the only source and remove the repo
copies. `qv launch` copies the bundled templates into each workspace's
`templates/starter/` folder. The repo's `templates/` holds only the
contributor boilerplate and the `community/` folder.

## Consequences
- One copy of each starter template; no drift.
- Contributors can't browse starters at the repo root; the contributing
  guide and the `community/` README point to the package location.
