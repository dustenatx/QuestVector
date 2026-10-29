# Decisions log

Architecture decision records (ADRs) for QuestVector. Each records one
significant choice: the context, what was decided, and the consequences. Start
a new record from [`0000-template.md`](0000-template.md) with the next number.
Records are never deleted; a reversed decision gets a new record that marks
the old one **Superseded**.

Records 0001–0006 and 0010 were written on 15 Oct 2026 to capture decisions
already made during the September 2026 build, from the code, commit history,
and README. Their dates are the date each decision first appears in the repo.

| # | Decision | Status | Date |
|---|---|---|---|
| [0001](0001-local-only-distribution.md) | Local-only distribution; nothing published externally | Accepted; narrowed by 0014 and 0016 | 2026-09-15 |
| [0002](0002-aes-256-gcm-local-vault.md) | AES-256-GCM encrypted local vault file | Accepted; KDF settings superseded by 0015 | 2026-09-09 |
| [0003](0003-reconciled-template-schema.md) | One reconciled mission-template schema | Accepted | 2026-09-09 |
| [0004](0004-data-driven-llm-provider-registry.md) | Data-driven LLM provider registry | Accepted | 2026-09-15 |
| [0005](0005-ollama-over-plain-http.md) | Ollama called over plain HTTP, no SDK | Accepted | 2026-09-15 |
| [0006](0006-independent-g-force-formula.md) | G-Force formula defined independently of the spec | Accepted | 2026-09-09 |
| [0007](0007-ci-validates-all-templates.md) | CI validates every template, not only changed ones | Accepted | 2026-10-15 |
| [0008](0008-ci-results-in-run-summary.md) | CI reports results in the run summary, not a PR comment | Accepted | 2026-10-15 |
| [0009](0009-bundled-starter-templates-only.md) | Bundled package templates are the only starter source | Accepted | 2026-10-15 |
| [0010](0010-single-source-version.md) | `__version__` is the single source of the version | Accepted | 2026-09-15 |
| [0011](0011-github-security-baseline.md) | GitHub security baseline modeled on risk-trainer | Accepted; partly superseded by 0013 | 2026-10-18 |
| [0012](0012-ollama-thinking-off.md) | Ollama requests switch thinking off | Accepted | 2026-10-20 |
| [0013](0013-python-3-14-uv-lock.md) | Python 3.14 only, managed with uv and a committed lock file | Accepted | 2026-10-27 |
| [0014](0014-github-releases.md) | Release files published to GitHub Releases | Accepted | 2026-10-28 |
| [0015](0015-pbkdf2-1m-iterations-vault-v2.md) | Vault key derivation: PBKDF2 at 1,000,000 iterations, settings stored in the file | Accepted | 2026-10-28 |
| [0016](0016-browser-app-static-pages.md) | Browser app served as static files from GitHub Pages | Accepted | 2026-10-28 |
| [0017](0017-bearing-quest-design-base.md) | Adopt the Bearing Quest design base | Accepted | 2026-10-29 |
