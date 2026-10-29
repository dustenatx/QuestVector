# QuestVector Backlog

Captured 15 Oct 2026. Work items to plan and discuss before implementation.
Each item notes what is already known from the 15 Oct review.

## 1. Review critical setup from the Gemini → Claude build
Audit the core decisions made across the two AI-directed stages for mistakes
or drift. Known starting points:
- **Two template schemas existed side by side.** The repo's `templates/` held
  the pre-reconciliation schema and failed validation; fixed on
  `fix/ci-and-repo-hygiene`. Check for other leftovers of the old schema
  (`narrative_weighting`, `jd_analysis_rules`) and decide whether the
  backward-compatibility path in `questvector/core/templates.py` is still needed.
- **README wording on testing.** The banner says the project "has never been
  tested"; the status table says "Implemented, tested, runs today." Both are
  partly true: the code is unit-tested with mocked AI providers, but narrative
  generation has never run against a live provider, because paid API access
  wasn't an option. Reword both to say exactly that. Items 8 and 9 close the gap.
- **Exit condition (agreed 15 Oct):** once items 8 and 9 pass, remove "never
  been tested" everywhere: the README banner, status table, and
  `docs/QuestVector_Spec.pdf`. Replace it with what was actually verified,
  naming the providers tested live (for example Gemini and a local Ollama
  model). Providers still tested only with mocks stay labeled that way. Keep
  "proof of concept" until the tool has been used in a real job search;
  passing tests aren't real-world use. Resume and dossier wording should change
  in step: update the "published as a proof of concept" project line only
  after reviewing it in the Applying for Jobs project.
- **Vault.** ✅ Done under item 13 (28 Oct 2026,
  [ADR-0015](decisions/0015-pbkdf2-1m-iterations-vault-v2.md)). Review key
  derivation, file permissions, and how the passphrase or key is supplied
  (`questvector/core/vault.py`). Known: PBKDF2-HMAC-SHA256 ran 390,000
  iterations; OWASP's current guidance is 600,000. Raising it needs a
  migration for existing vaults (see ADR-0002).
- **LLM data flow.** Confirm exactly what dossier content is sent to remote
  providers and that the user sees it before it leaves the machine.
- **Keyword normalization in matching.** Found 15 Oct: the tokenizer turns
  "CI/CD" in a job description into `ci/cd`, but the DevOps starter template's
  keyword is `cicd`, so they never match. Similar risks: "SOC 2" vs `soc2`,
  "K8s" vs `kubernetes`. Review tokenizer normalization and the starter
  templates' keyword forms together; add tests for common variants.
- **Negative statements match as keywords.** Found 18 Oct while converting
  a real dossier: matching is by keyword, so a bullet such as "no hands-on
  Kubernetes" or "never used HashiCorp Vault" counts as a Kubernetes or
  Vault match, and narrative generation may present it as a skill. Today
  the only protection is leaving such statements out of the dossier, which
  the README doesn't mention. Options to weigh: document the rule in the
  README's dossier section; have `qv` warn when a bullet contains a negation
  ("no", "not", "never", "training only") next to a keyword; or support an
  explicit exclusions section that matching ignores. Add a test with a
  negated skill either way.
- **Role titles in headings may not count toward matching.** Found 18 Oct
  with a synthetic dossier: the match reported `manager` as a gap although
  the role headings say "Engineering Manager". Check whether the parser
  excludes `##` headings from the keyword set, and add a test.
- **Spec traceability.** Code cites `MASTER_DEVELOPER_SPEC.pdf` section numbers;
  that file isn't in the repo. Decide whether to add it, or re-point citations
  to `docs/QuestVector_Spec.pdf`.

## 2. GitHub configuration, modeled on risk-trainer
✅ Done 18 Oct 2026 ([ADR-0011](decisions/0011-github-security-baseline.md)):
actions pinned to SHAs; gitleaks, Semgrep, and pip-audit in CI; Dependabot
version updates; `SECURITY.md`. Repository settings (the `main` ruleset with
no bypass, squash-only merges, private vulnerability reporting) are applied
once the pull request merges. The Claude review workflow was left out; the
lock file for pip-audit moves to item 11.
Compare against risk-trainer's scanning and repository settings and adopt
what fits a local-only Python app. Candidates: branch protection on `main`,
required status checks, Dependabot (pip and GitHub Actions), CodeQL or
Semgrep, secret scanning with push protection, and pinning actions to commit
SHAs.

## 3. Fix spec Section 10.2
Correction (15 Oct): Section 10.2 never listed the old `templates/` files.
Its real gaps are omissions. The repository layout it shows leaves out
`templates/` (boilerplate and `community/`), `.github/` (issue templates and
the workflow), and now `CHANGELOG.md`, `docs/PRD.md`, `docs/BACKLOG.md`, and
`docs/decisions/`. Regenerate the PDF from its source with the current
layout, and check Section 11's quality claims (mypy and pyflakes clean) at
the same time, since CI doesn't verify them yet.
- **Vault settings (found 28 Oct, item 13).** §3.1's table (page 5) still
  says "PBKDF2-HMAC-SHA256, 390,000 iterations" and describes only a salt
  and nonce per save. Update it per
  [ADR-0015](decisions/0015-pbkdf2-1m-iterations-vault-v2.md): 1,000,000
  iterations (600,000 minimum, 5,000,000 cap on read), format 2 with the KDF
  name, iterations, and salt stored in the file and authenticated, format 1
  files upgraded on next save, atomic saves, and Windows file access coming
  from the folder's permissions. Pages 4 and 12 only say "AES-256-GCM",
  which is still true.

## 4. Unit tests: CI and optional-extras failures
✅ Done 18 Oct 2026, except desktop interface testing, which moves to
items 6 and 15 (Playwright). `tests.yml` runs pytest (Python 3.12 and 3.13,
90% coverage floor), a run without AI extras, and mypy plus pyflakes. The
13 SDK tests skip cleanly without their packages.
- The 142 tests never run in CI; only template validation does. Add a
  `pytest` job (with coverage) on pull requests and pushes to `main`.
- 13 tests in `tests/test_llm.py` fail with `ModuleNotFoundError` unless the
  `[llm]` extra is installed. They should skip cleanly (for example
  `pytest.importorskip`) or CI should install `.[dev,llm]` explicitly.
- Decide how to test the desktop app (`tests/test_desktop_api.py` covers the
  Python bridge only, not the web UI).

## 5. Bring resume lessons from the Applying for Jobs project into export
The job-search project has hard-won rules for ATS-safe resumes that
QuestVector's PDF/DOCX export (`questvector/core/exporter.py`) likely doesn't
follow yet. Evaluate adopting:
- Single column, no tables, text boxes, columns, tab stops, or header/footer
  content.
- Two-line role headers with the employer repeated on every role;
  `Mon YYYY – Mon YYYY` dates.
- Real hyperlinks for email and profile URLs.
- A 20-year date cutoff with a dateless "Earlier Career" line.
- An automated ATS check (an adaptation of `ats_check.py`): extraction across
  three parsers, page count, third-person pronouns, AI-tell phrases, and
  overused words.
- Narrative prompt guardrails: no invented metrics, titles, or technology
  claims, and no pronoun leaks.
Also look for gaps beyond ATS, such as cover-letter output and job-fit reads.

## 6. MCP servers and tooling for code quality and coverage
Add development-time MCP servers as in risk-trainer, for example Playwright
(desktop web UI testing) and Semgrep (static analysis). Also consider:
coverage thresholds, `ruff` linting and formatting, `mypy` type checking,
pre-commit hooks, and `pip-audit` for dependency vulnerabilities. The app
runs locally, but these improve quality without changing that.

## 7. Moved
Originally "Further topics to discuss"; now item 11. Numbers are kept
stable so references elsewhere stay valid.

## 8. Live-test narrative generation through an API at no cost
The 13 provider tests use mocked clients; no real API call has ever been
made. Find a no-cost way to run end-to-end tests against a real remote
provider. Options to research (verify current terms before relying on any):
- A free tier from one of the three supported providers, such as Google
  AI Studio's Gemini API, which has offered free-tier access.
- Free tiers or free models on services with OpenAI-compatible APIs, which
  might work through the existing `openai` provider with a custom base URL.
  Check whether `questvector/core/llm.py` supports a base-URL override.
Constraints: no payment method on file if it can be avoided, stay within
free-tier rate limits, and send only synthetic test data, never the real
dossier, since free tiers may use inputs for training. Deliverable: an opt-in
live test (skipped by default, for example behind an environment variable)
and a short how-to.

## 9. Install and configure a local LLM (Ollama) for learning and testing
Partly done 20 Oct 2026 ([ADR-0012](decisions/0012-ollama-thinking-off.md)):
Ollama 0.40.6 installed with llama3.1:8b, qwen3.5:9b-q4_K_M, and
gemma4:12b-it-q4_K_M, compared on synthetic data. gemma4 had no invented
facts in 5 runs; the other two invented facts in 3 of 5. The opt-in live
test and its synthetic fixtures are in `tests/`, with a how-to in
`docs/DEVELOPMENT.md`. The live runs found three bugs, now fixed:
- A slow response raised a raw `TimeoutError`.
- A missing model was reported as an unreachable server.
- Thinking models spent the whole token limit reasoning and returned
  nothing. Thinking is now switched off.

Done 27 Oct 2026: the owner ran narrative generation on the real dossier,
and `DEFAULT_OLLAMA_MODEL` changed from llama3.1 to gemma4:12b-it-q4_K_M,
on ADR-0012's comparison and that run.

Follow-ups found in the PR #7 review (20 Oct 2026), not yet fixed:
- **Connection reset mid-response.** If the Ollama server stops partway
  through a reply, `http.client.RemoteDisconnected` (an `OSError`, not a
  `URLError`) escapes `OllamaNarrativeGenerator.generate` as a raw
  traceback, the same class of bug as the timeout. Wrap it in `LLMError`
  and add a test.
- **`qv vault set-key` resets the timeout.** Running it again without
  `--timeout` sets `llm_timeout` back to the default, as `--host` already
  does for the host. Decide whether unset flags should keep the stored
  values, and document the behavior either way.
- **Desktop prompt omits the template's tone.** `qv export --narrative`
  passes the template's `tone_style` to `build_narrative_prompt`; the
  desktop app's Generate Narrative doesn't. Make the two build the same
  prompt, with a test.

Set up Ollama on the Mac and choose a model that suits this project: drafting
a short, accurate resume summary from dossier text. Goals:
- Learn how a local model is installed, pulled, served, and called.
- Pick a model size the machine's memory can run comfortably; compare two or
  three candidates on the same prompt for accuracy and invented facts.
- Configure QuestVector with `qv vault set-key --provider ollama`, then run
  narrative generation end to end with the real dossier, which never leaves
  the machine.
- Add an opt-in live test against the local server and document the setup.
This becomes the zero-cost, fully private path for real testing, and is the
fourth provider's first real-world use.

## 10. Documentation, decisions log, PRD, and changelog
✅ Complete 15 Oct 2026, except the PRD, which is a draft awaiting owner review.
Bring the project's written record up to the standard used for risk-trainer,
whose PRD and status docs live in the Applying for Jobs project
(`claude/risk-trainer-prd.md`, `claude/risk-trainer-status.md`) and can serve
as models.
- **PRD.** ✅ First draft 15 Oct 2026: `docs/PRD.md` (version 0.1, for owner
  review). Original scope: write a product requirements document: problem, target user,
  goals and non-goals (including the local-only distribution policy), feature
  requirements with acceptance criteria, and open questions. Reconcile it with
  the original design spec and `docs/QuestVector_Spec.pdf` so the three don't
  contradict each other.
- **Decisions log.** ✅ Done 15 Oct 2026: `docs/decisions/` holds ten records.
  Original scope: start `docs/decisions/` with short architecture decision
  records. Backfill the decisions already made: local-only with no hosted
  service; the AES-256-GCM vault; the reconciled template schema; the
  data-driven provider registry; Ollama over plain HTTP with no SDK; the G-Force
  formula defined independently of the spec; templates validated in full
  rather than by diff in CI; results in the run summary rather than a PR comment.
- **Changelog.** ✅ Done 15 Oct 2026. Original scope: add `CHANGELOG.md` in the Keep a Changelog format, tied to
  `questvector.__version__`, with backfilled entries from the git history and
  a convention for keeping it current on every merge.
- **Documentation review.** ✅ Done 15 Oct 2026: README, contributing guide,
  issue templates, and dev extras fixed; `docs/DEVELOPMENT.md` added; every
  Quickstart command run and confirmed working. A separate user guide was not
  needed yet; the README's dossier section covers it. Original scope: check the README, contributing guide, spec, and
  module docstrings against the code; consider a `docs/` index, a user guide
  separate from the README, and a developer setup guide.

## 11. Further topics to discuss
- ✅ Done 28 Oct 2026 ([ADR-0014](decisions/0014-github-releases.md)):
  release and versioning: tagged releases tied to the changelog (item 10),
  and how users get updates without a hosted service. Pushing a `v*` tag
  (owner only) publishes a pre-release on GitHub Releases with the wheel,
  sdist, `SHA256SUMS`, and build provenance; notes come from the changelog.
  First release: 1.1.0.
- ✅ Done 27 Oct 2026 ([ADR-0013](decisions/0013-python-3-14-uv-lock.md)):
  a dependency lock file, so pip-audit (item 2) checks fixed versions
  rather than whatever pip resolves on the day it runs. Adopted with the
  engineering baseline: Python 3.14 only, uv, a committed `uv.lock`
  (7-day cooldown), and CI moved to uv.
- Packaging and install experience across macOS, Windows, and Linux
  (pywebview's platform dependencies; Python 3.14 requirement).
- Privacy documentation: a short threat model for local data and the vault.
- Accuracy of public claims: the README, spec, and resume wording ("142-test
  automated suite," "proof of concept") should stay consistent as this
  changes.
- Remaining issue templates and the contributing guide, now that CI works.
- Whether the Web Cockpit roadmap stays in the README or moves to its own
  document.

## 12. "New things learned" document
QuestVector was the owner's first vibe-coding project, and it introduced
many other practices along the way. Write `docs/LEARNED.md` recording what
was new and what each taught. Walk through it together first: review the
commit history, decisions log, and this backlog to identify what was done
before versus new. Candidate topics: AI-directed development with Gemini and
Claude, Python packaging and optional extras, encrypted storage and key
derivation, GitHub Actions, Dependabot, ADRs, Keep a Changelog, and local LLMs.
Useful as interview material and for the instructor pivot.

## 13. Vault hardening
✅ Done 28 Oct 2026 ([ADR-0015](decisions/0015-pbkdf2-1m-iterations-vault-v2.md)):
PBKDF2-HMAC-SHA256 at 1,000,000 iterations (Argon2id considered, not chosen);
vault format 2 stores the KDF name, iterations, and salt and authenticates
them; format 1 vaults open and upgrade on next save; atomic owner-only
saves; a new vault refuses an empty passphrase and the CLI asks for it
twice; `tests/test_secrets_never_leak.py` covers output, errors, logs,
bundles, and the vault file, and SDK error messages are now redacted.
Passphrase entry was already `getpass` only (no flag or environment
variable). The desktop confirmation field is left for item 15.

Separate from the broader vault review in item 1.
- Raise key derivation to current OWASP guidance: PBKDF2-HMAC-SHA256 at
  600,000 iterations or more (now 390,000), or move to scrypt or Argon2.
  Record the choice as a new ADR.
- Store the KDF parameters in the vault file so future changes don't break
  old vaults, and re-encrypt older vaults on next save without re-entering
  keys (PRD R17).
- Add a test confirming keys never appear in command output, error messages,
  or exported bundles.
- Review how the passphrase is entered (no echo, no shell history) and what
  happens on Windows, where file permissions are best-effort.

## 14. Discuss desktop-style use hosted on AWS
Discussion item, not yet a decision. Explore running QuestVector on AWS so it
can be used from any device rather than only from a local install.

**Decided 28 Oct 2026:** the self-host cloud kit isn't pursued for
less-technical users. The browser app (item 16,
[ADR-0016](decisions/0016-browser-app-static-pages.md)) serves them. A
private deployment for the owner stays open for discussion.

**Conflicts with an accepted decision.** ADR-0001 says nothing is hosted or
published externally, ever, and the README and spec repeat it. Any hosted
option needs a new ADR that supersedes or narrows ADR-0001, and the README,
spec, and PRD non-goals updated to match.

Options to compare:
- **Private, single-user deployment in the owner's own AWS account.** The
  closest fit to the local-first intent: the owner is still the only person
  with the data. Variants:
  - The existing desktop web UI served as a web app (Lambda behind
    CloudFront, as in risk-trainer), with the Python bridge calls becoming
    API calls.
  - The desktop app itself on a cloud desktop (an EC2 instance with remote
    display, or Amazon WorkSpaces). Least code change; likely not free.
- **Self-host kit for other users.** Terraform others deploy into their own
  AWS accounts, so each user keeps their own data. Keeps the spirit of
  ADR-0001 (no shared service holding anyone else's data).
- **Shared multi-user service.** Accounts, tenant isolation, and holding
  other people's career data. The largest change in scope, risk, and cost;
  likely out of scope.

Questions to settle:
- **Data storage.** Where the dossier and bundles live (S3 with encryption),
  and whether a user can still edit plain Markdown files.
- **Secrets.** The vault's replacement: SSM Parameter Store SecureString or
  Secrets Manager, and whether the passphrase model still applies.
- **Authentication.** Even a single-user deployment needs sign-in so the
  dossier isn't public.
- **Local AI.** Ollama needs compute that the always-free tier doesn't
  provide, so the $0 local-model path (item 9) would stay desktop-only.
- **Cost.** Can it stay at $0 within always-free limits, as risk-trainer
  does? Verify current AWS free-tier terms before deciding.
- **Security baseline.** Reuse risk-trainer's controls: least-privilege IAM,
  OIDC deploys with an approval gate, WAF and rate limits, budget alarms.

Related: the browser-only app is item 16
([ADR-0016](decisions/0016-browser-app-static-pages.md); evidence in
[`docs/spikes/2026-10-browser-pyodide.md`](spikes/2026-10-browser-pyodide.md)).

Career relevance: an AWS-hosted variant would show AWS architecture,
Terraform, and security design on a second project, alongside risk-trainer.

## 15. UI/UX consistency with risk-trainer
Review the desktop app's interface so it is consistent with risk-trainer and
offers comparable features, adapted to a desktop app rather than a website.

**Design base (29 Oct 2026, [ADR-0017](decisions/0017-bearing-quest-design-base.md)):**
QuestVector uses the Bearing Quest design system as its shared base (color
tokens, fonts, logo, accent and data-color rules, contrast test) and keeps
the Flight Deck instrument-panel motif. Its own accent color is still to be
chosen.

Before any UI code:
1. Choose QuestVector's accent and contrast-check it in both themes.
2. Build a screens mockup from the design system, before the item 16
   phase (c) app shell.
3. The desktop (pywebview) window and the browser app share one
   stylesheet.
4. The first UI pull request adds the token contrast test (WCAG 2.2 AA;
   3:1 for focus rings and control outlines) and the CSS custom properties
   generated from the design system's `tokens.json`.

**Applies to both apps (28 Oct 2026):** this UI work covers the desktop app
and the browser app (item 16). Build it once where the two can share the
interface.

Starting facts (quick scan, 16 Oct): the interface is about 550 lines of
plain HTML, CSS, and JavaScript in `questvector/desktop/web/`, themed as the
"Tactical Ops Flight Deck" HUD. It already loads no external scripts or
inline scripts. It has one ARIA attribute, no visible focus styles, no
responsive layout rules, and no light/dark handling.

Compare against risk-trainer's PRD requirements and look:
- **Accessibility:** WCAG 2.2 AA target, labels on every input, visible
  focus, keyboard-only use, color never the only signal. The G-Force gauge
  and alert colors need a text equivalent.
- **Layout:** usable at small window sizes (risk-trainer targets 360 px).
- **Help and reference content:** risk-trainer has About, Privacy, and a
  reference page. QuestVector equivalents: a short first-run explanation, a
  page explaining the score (PRD R5), the dossier format, and a privacy page
  stating what stays local and what a remote AI provider receives (PRD R13).
- **Result presentation:** risk-trainer's debrief explains each result.
  Apply the same to a match: why each category scored as it did, which
  keywords matched, and what to add to the dossier.
- **Errors:** plain-language messages; no stack traces shown.
- **Vault passphrase confirmation (added 28 Oct, item 13):** the Vault panel
  has one passphrase field, so creating a vault from the desktop app can't
  catch a typo; `qv vault set-key` asks twice. Add a confirmation field
  shown only when the workspace has no vault yet. An empty passphrase is
  already refused for a new vault, from both the CLI and the desktop.
- **Content Security Policy:** risk-trainer enforces a strict CSP with no
  inline scripts; set the same in `index.html`.
- **Visual identity:** decided 16 Oct: keep the Flight Deck look, and share
  conventions with risk-trainer where they make sense (accessibility,
  layout behavior, help pages, error handling, CSP), not its visual design.
  Updated 29 Oct by [ADR-0017](decisions/0017-bearing-quest-design-base.md):
  the Flight Deck motif now sits on the Bearing Quest base.
- **Terminology (undecided, review later; still open after ADR-0017,
  pending mockups):** the HUD vocabulary
  ("Sync-AST," "Lock-On Red," "Afterburner Amber," "G-Force") may confuse
  new users. Make quick mockups of two or three labeling options (themed
  only, plain only, plain with themed names secondary) and decide from them.

Needs risk-trainer's front-end code (templates and CSS), not just its PRD,
for a side-by-side comparison. Pairs with PRD R19 (Playwright tests for each
tab) and backlog item 6.

## 16. Browser-only app
Decided 28 Oct 2026 ([ADR-0016](decisions/0016-browser-app-static-pages.md)):
a browser app for less-technical users who can't install software. It's
static files on this repository's GitHub Pages site, running the existing
Python core in Pyodide, with data kept in the browser. The desktop app and
CLI continue. Requirements: PRD §5.9, R22–R28. Evidence and measurements:
[`docs/spikes/2026-10-browser-pyodide.md`](spikes/2026-10-browser-pyodide.md).

Work in phases, one pull request each:
- **(a) pywebview becomes a desktop extra.** Today it's a hard dependency,
  and its sdist-only dependency `proxy-tools` blocks a normal micropip
  install. Move it to an extra (for example `desktop`), and update the
  install docs and how `qv` starts the desktop app. Needs an ADR.
- **(b) Core API for the browser.**
  - Bytes-in/bytes-out variants of export and the vault functions, next to
    the path-based ones.
  - A pluggable key-derivation function and cipher for the vault, so the
    browser can use WebCrypto (R24) with the vault format unchanged.
- **(c) App shell and storage adapter.**
  - The page, Pyodide in a Web Worker (R22), and export libraries loaded on
    demand (R25).
  - The storage adapter: folder access on Chromium; upload, download and
    browser-private storage elsewhere; persistent storage and backup prompts
    (R23).
  - Pinned, self-hosted, hash-checked assets (R27) and the strict CSP (R26).
  - The look: see item 15 ([ADR-0017](decisions/0017-bearing-quest-design-base.md)).
- **(d) Pyodide CI job.**
  - Run the test suite under Pyodide, on Pyodide's own package versions.
  - It's a new required check under ADR-0011: update
    `.github/rulesets/main.json` in the same pull request, and re-apply the
    ruleset after merging.
- **(e) Deploy to GitHub Pages.**
  - A tag-only workflow, on the same `v*` tags as releases, with the same
    checks as `release.yml`.
  - Check whether Pages compresses `application/wasm`.
  - Add the frame check that refuses to render inside a frame. It's a
    guardrail, not a control (ADR-0016).
  - Update `SECURITY.md` when the site goes live, putting the site in scope
    for reports.
  - Owner's manual steps:
    1. In the repository settings, set the Pages source to **GitHub
       Actions**.
    2. Limit the `github-pages` deployment environment to `v*` tags.
- **(f) AI in the browser, after item 8.** A browser transport for the
  providers, added through the registry, and the browser vault with
  WebCrypto (R24, R28).

Not measured yet, and worth checking before or during phase (c): first-load
time on slower machines and slow connections, and Edge. Mobile isn't a goal
until it's tested (PRD G8).

