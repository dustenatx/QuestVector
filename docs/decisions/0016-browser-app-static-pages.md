# 0016. Browser app served as static files from GitHub Pages

- **Status:** Accepted
- **Date:** 2026-10-28

## Context
The desktop app needs Python 3.14 and `pip`. Many job seekers QuestVector
could help can't install software, or don't have admin rights on the computer
they use. [ADR-0001](0001-local-only-distribution.md) rules out any hosted
service. [ADR-0014](0014-github-releases.md) allows only release files on
GitHub Releases.

Options considered:
- **The self-host cloud kit** (backlog item 14): Terraform that users deploy
  into their own AWS accounts. Far too technical for these users. Not pursued
  for them.
- **The planned Web Cockpit:** a React/Tailwind UI with a Rust-compiled Wasm
  core, built and served from `localhost`. It means a second engine in a
  second language, and its scores could differ from the Python build's.
  Users would still have to clone and build it.
- **A static site running the existing Python core in Pyodide, with data in
  the browser.** Chosen.

The browser/Pyodide spike
([`docs/spikes/2026-10-browser-pyodide.md`](../spikes/2026-10-browser-pyodide.md))
tested the third option on 28 Oct 2026, using synthetic data only:
- **The core runs unchanged** in Pyodide 314.0.7 (Python 3.14.2) in Chrome 156,
  Safari 27.2 and Firefox 150. That covers parsing, matching, DOCX and PDF
  export, and the vault round trip. The results are identical to native
  CPython.
- **Strict CSP:** zero violations with
  `script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'`. `'unsafe-eval'`
  isn't needed.
- **First load:** 14.4 MB compressed. On the owner's Mac the app is usable
  about 3.1 s after the files arrive in Chrome and Safari, and 3.8 s in
  Firefox.
- **Key derivation:** WebCrypto is 3–5× faster than Pyodide's `cryptography`
  build (129 ms against 660 ms in Chrome), doesn't freeze the page, and
  derives the same key.
- **Blockers found:**
  - pywebview's dependency `proxy-tools` exists only as an sdist, which
    blocks a normal micropip install.
  - AI calls use blocking HTTP, which a browser can't do.
- **Not tested:** Edge, mobile browsers, slower machines and slow
  connections.

## Decision
This narrows ADR-0001 as ADR-0014 did; the rest of ADR-0001 stands. It
supersedes the planned React/Rust Web Cockpit.

- **A browser app**, served as static files from this repository's GitHub
  Pages site, runs the existing Python core in Pyodide. It is for
  less-technical users on current desktop browsers. The desktop app and CLI
  continue. There is one engine, so both apps give identical scores.
- **Static files only:**
  - no backend
  - no accounts
  - no data collection
  - no analytics or telemetry.
  
  Career data stays in the user's browser, or in a folder they choose.
- **No third-party scripts at run time.** Pyodide and every wheel are
  self-hosted on the same site, pinned to exact versions, and checked
  against known hashes when the site is built. The page loads nothing from a
  CDN.
- **Deploys only from owner-created `v*` tags,** the same tags as releases.
  They fall under ADR-0014's tag ruleset, so only the owner can start a
  deploy, and a release and the site always share a version. The deploy
  workflow runs the same tag checks as `release.yml`: the tagged commit is on
  `main` and the tag matches `questvector.__version__`.
- **A strict CSP is part of the design:** the spike's policy, plus
  `worker-src 'self'` for the Web Worker that runs Pyodide.

## Consequences
- **The CSP is a `<meta>` tag, and framing can't be blocked.** GitHub Pages
  can't set response headers, so the CSP has to be a `<meta>` tag, which
  can't enforce `frame-ancestors`. Another site could load the app in a
  frame (clickjacking). The owner accepted this risk on 28 Oct 2026.
  Backlog item 16 phase (e) adds a script that refuses to render the app
  inside a frame. It is a **guardrail, not a control**: a script can be
  blocked or bypassed in ways a response header can't.
- **Caching is Pages' own.** Pages sets a short cache lifetime (about 10
  minutes). Whether it compresses `application/wasm` isn't verified (phase
  e); without compression, the first load is about 22 MB rather than 14 MB.
- **Pyodide pins need manual updates.** Dependabot doesn't track the
  Pyodide and wheel pins, so updating them is a deliberate change with new
  hashes.
- **Browser storage can be cleared**, by the browser or by the user. The
  app asks for persistent storage and prompts users to download backups.
  Only Chromium browsers can work on a real folder; Safari and Firefox users
  upload and download their files.
- **No AI in the first browser version.** AI calls need a browser transport,
  and live provider testing (backlog item 8) comes first.
- **Required checks change later.** A Pyodide CI job will be a new required
  check under [ADR-0011](0011-github-security-baseline.md), with
  `.github/rulesets/main.json` updated in the same change.
- **Docs to keep in line.** The PRD (G8, §5.9), the README and backlog item
  16 follow this record. `SECURITY.md`, which says there is no hosted
  service, is updated when the site goes live.
- **What's still not allowed:** no PyPI or npm package, no custom domain
  (the site lives at the repository's `github.io` address), and no
  telemetry.
