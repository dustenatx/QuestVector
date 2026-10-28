# 0014. Release files published to GitHub Releases

- **Status:** Accepted
- **Date:** 2026-10-28

## Context
[ADR-0001](0001-local-only-distribution.md) says nothing is published
externally, including "no package-registry release": users clone the
repository and install from source. That leaves no versioned file a user can
download and check, and updates mean `git pull`. ADR-0013 expected GitHub
Releases to ship wheels later.

On 25 Oct 2026 the owner decided to distribute through GitHub Releases only.
Options considered:
- **PyPI.** One `pip install questvector`, but a public package registry is
  exactly what ADR-0001 rules out, and the name and account become something
  to defend. Rejected.
- **A third-party release action.** Another supply-chain dependency with
  write access. Rejected: `gh`, preinstalled on GitHub's runners, does the
  same.
- **A signed macOS app.** Needs a paid Apple developer account and a
  separate packaging path. Rejected for now.
- **GitHub Releases, files only.** Chosen.

## Decision
This narrows ADR-0001; the rest of it stands.
- CI (`.github/workflows/release.yml`) may publish the wheel, the sdist, and
  a `SHA256SUMS` file to this repository's GitHub Releases. It runs only when
  a `v*` tag is pushed, never on pull requests or branches.
- The run tests the tagged commit, checks it is on `main` and that the tag
  equals `questvector.__version__`, builds, and writes SLSA build provenance
  for the wheel and sdist with `actions/attest`. The release notes are that
  version's section of `CHANGELOG.md`.
- The repository's immutable-releases setting is on, so a published release
  can't be changed. The workflow creates a draft, attests, and publishes the
  draft as its last step, so a failure leaves at most a draft. A bad release
  is fixed with a new patch version, never by editing the published one.
- Releases are marked pre-release while the README banner says the project
  is a proof of concept (backlog item 1's exit condition).
- The build backend is pinned to an exact setuptools version, at least 7
  days old, so a release isn't built with whatever setuptools is newest that
  day. Build requirements are outside `uv.lock`.
- **Tag ruleset** (`.github/rulesets/tags.json`): creating, updating, and
  deleting `v*` tags is restricted, with a bypass for the repository admin
  role only, so only the owner can start a release. This is a deliberate
  exception to [ADR-0011](0011-github-security-baseline.md)'s no-bypass
  rule. It covers release tags only; the `main` ruleset keeps no bypass.
- The application itself makes no new network calls. There is still no
  PyPI package, hosted service, or telemetry.

## Consequences
- Users can download a versioned wheel and check it with
  `shasum -a 256 -c SHA256SUMS` and `gh attestation verify`. The second needs
  the GitHub CLI installed and signed in.
- `pip install` of the wheel still downloads its dependencies from PyPI.
- The release jobs are not required checks and aren't in `main.json`;
  `tags.json` and the immutable-releases setting are applied by hand, so the
  live settings can drift from the repository, as with `main.json`.
- A mistake in a published release costs a version number.
- The pinned setuptools has to be bumped deliberately (Dependabot is expected
  to propose it; see `docs/DEVELOPMENT.md`).
