# 0006. G-Force formula defined independently of the spec

- **Status:** Accepted
- **Date:** 2026-09-09

## Context
The spec names a "G-Force" match score and shows a sample result, but never
defines how it is calculated.

## Decision
Define and document a formula rather than guess at an unpublished one. For
each template category, coverage is the share of the category's keywords
found in the job description that also appear in the dossier. The score is
the weight-normalized sum of weight × coverage, as a percentage. A heavily
weighted category with zero coverage is a red flag; missed keywords in
partly covered categories are gaps. The full algorithm is documented in
`questvector/core/matcher.py`.

## Consequences
- Scores are explainable and reproducible from the documented rules.
- Keyword matching misses synonyms and context ("led incident response" vs.
  "incident commander"), so scores are a guide, not a verdict.
- A future Web Cockpit is not guaranteed to produce identical scores.
