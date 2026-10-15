# 0001. Local-only distribution; nothing published externally

- **Status:** Accepted
- **Date:** 2026-09-15

## Context
The original design spec used a "Zero-Cloud" framing and named a hosted Web
Cockpit, a public domain, and an npm package. A career dossier is personal
data, and a hosted service adds cost, an attack surface, and an operator who
can see user data.

## Decision
Nothing is published externally, for either implementation: no public
domain, no hosted service, no package-registry release. Users clone the
repository and run it locally. The planned Web Cockpit would be built
locally and served from `localhost`. The only outbound network calls are to
a remote LLM provider, and only when the user configures one and explicitly
asks for narrative generation.

## Consequences
- User data stays on the user's machine unless they choose a remote provider.
- Installing requires Python and `pip`; there is no one-click installer.
- Updates come from `git pull`, so release notes in `CHANGELOG.md` matter.
- Any URL or `npx`/`npm install` command claiming to be QuestVector is not real.
