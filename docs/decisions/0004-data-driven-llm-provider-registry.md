# 0004. Data-driven LLM provider registry

- **Status:** Accepted
- **Date:** 2026-09-15

## Context
Narrative generation first supported only Anthropic. Users may have an
account with a different provider, or want no remote provider at all.
Hardcoding each provider in the CLI, vault, and desktop UI would spread
provider logic across the codebase.

## Decision
Define providers in one registry, `PROVIDERS` in `questvector/core/llm.py`.
Each entry pairs provider metadata (name, setup link, caveats, default
model) with a factory function returning an object that satisfies the
`NarrativeGenerator` protocol. The CLI's `--provider` choices and the
desktop provider picker read the registry directly. Each cloud SDK is an
optional install extra (`llm-anthropic`, `llm-openai`, `llm-gemini`, or `llm`
for all three).

## Consequences
- Adding a provider means a generator class, a factory, and one registry
  entry, with no CLI, vault, or UI changes. A test checks this.
- Core installs don't pull in SDKs the user won't use.
- Tests for providers whose SDK isn't installed currently fail instead of
  skipping (backlog item 4).
