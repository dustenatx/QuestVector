# Spike: QuestVector's Python core in a browser tab via Pyodide

- **Date:** 28 Oct 2026
- **Status:** Go with changes, 28 Oct 2026
  ([ADR-0016](../decisions/0016-browser-app-static-pages.md); built under
  backlog item 16). All seven points have findings.
  - Done: the PyPI dependency probe (point 2), the Chrome measurements
    (point 4) and the strict-CSP run (point 5), all run by the owner in
    Chrome 156 on macOS on 28 Oct 2026.
  - Done: the three-browser file checks (point 6), and one first load of
    the core page each in Safari 27.2 and Firefox 150.
- **Question:** For less-technical users who can't install software, could
  QuestVector be a browser-only app, served as static files (for example
  from GitHub Pages), running the existing Python core through Pyodide with
  data kept in the browser?
- **Scope:** A time-boxed experiment (one working session), not a feature.
  `questvector/`, `tests/`, `pyproject.toml`, `uv.lock` and CI are
  unchanged. The prototype is in
  [`spikes/browser-pyodide/`](../../spikes/browser-pyodide/README.md) and
  runs only on 127.0.0.1 with synthetic fixtures. The PRD change and an ADR
  come after the go/stop decision.

## Summary

The unmodified core runs in Pyodide in Chrome, Safari and Firefox under a
strict Content Security Policy, with no CSP violations. Every step works: dossier parsing,
matching against a starter template, DOCX and PDF export (the owner checked
both files), and the vault round trip (including opening a format 1 vault).
The results match native CPython exactly. On a first load, the app is
usable about 3 s after the files arrive. Three things need
to change before this could be a product:

1. pywebview must become an optional dependency.
2. AI calls need a browser transport.
3. Vault key derivation should use WebCrypto, and the vault needs a browser
   storage home.

The first load is large: 21.7 MB uncompressed, and 14.4 MB as jsDelivr
actually served it compressed. **Recommendation: go with changes.**

## 1. Pyodide version

| | |
|---|---|
| Version | **314.0.7** (Python 3.14.2, Emscripten 5.0.3, ABI `2026_0`) |
| Released | 14 Sep 2026 (44 days before this spike) |
| Why this one | The newest release at least 7 days old on the current line. 0.29.5 and 0.27.8 came out later (16 Sep 2026), but they are maintenance releases of older lines on older Pythons. Pyodide 314 is the first line on Python 3.14, which matches `requires-python >=3.14` (ADR-0013). |
| Pinning | `stage.py` fetches `pyodide@314.0.7` from npm and checks the tarball's sha512 integrity. Package wheels are checked against the sha256 in that tarball's `pyodide-lock.json`. The CDN run loads `cdn.jsdelivr.net/pyodide/v314.0.7/full/`. |

## 2. Loading the core

The questvector 1.1.0 wheel was built from `main` (`ebc389c`) with
`uv build --wheel`. Everything else in the table below was installed into
Pyodide with micropip from local files, with no index.

| Dependency (lock version) | Loads | From | Version in Pyodide |
|---|---|---|---|
| PyYAML (6.0.3) | Yes | Pyodide build | 6.0.3 |
| cryptography (50.0.2) | Yes | Pyodide build | **47.0.0** |
| cffi (2.1.1) | Yes | Pyodide build | **2.0.0** |
| pycparser | Yes | Pyodide build | 3.0 |
| python-docx (1.2.0) | Yes | PyPI, pure-Python wheel | 1.2.0 |
| lxml (6.1.3) | Yes | Pyodide build | 6.1.3 |
| reportlab (5.0.1) | Yes | PyPI, pure-Python wheel | 5.0.1 |
| Pillow (13.0.0) | Yes | Pyodide build | **12.2.0** |
| charset-normalizer (3.5.2) | Yes | Pyodide build | **3.4.7** |
| typing-extensions (4.16.0) | Yes | Pyodide build | **4.15.0** |
| pywebview (6.2.1) | **No (not needed)** | Pure-Python wheel on PyPI, but its dependency `proxy-tools` 0.1.0 is published only as an sdist, and micropip can't install sdists | none |
| bottle (0.13.4) | Not installed | Pure-Python wheel on PyPI (pywebview dependency) | none |
| anthropic, openai, google-genai (`llm-*` extras) | Not tried | See point 7 | none |

Bold marks a version that differs from `uv.lock`. Pyodide pins its own
builds, so a browser build would run on older cryptography, cffi and Pillow
than CI tests against.

**`micropip.install(questvector)` with normal dependency resolution fails**,
because it reaches pywebview, then proxy-tools, which exists only as an
sdist. The owner confirmed it in Chrome with the `?probe` page, which lets
micropip resolve dependencies from PyPI. The error was:

```
ValueError: Can't find a pure Python 3 wheel for 'proxy-tools'.
```

The spike installs the wheel with `deps=False` instead, and everything
after that passes. The core never imports pywebview; only
`questvector/desktop/` does.

## 3. Running the core on synthetic data

Fixtures: `tests/fixtures/ollama_live/` (dossier and job description) and
`tests/fixtures/vault/v1-vault.json`. Every step calls the unmodified core
from [`steps.py`](../../spikes/browser-pyodide/steps.py).

Chrome times are the median of the three self-hosted first loads. The
other Chrome runs were within a few milliseconds.

| Step | Result | Chrome 156 (ms) | Node smoke (ms) |
|---|---|---|---|
| Import the core (`exporter`, `vault`, `matcher`, and with them python-docx, lxml, reportlab, cryptography) | Pass | 812 | not separate |
| `init_workspace` + `WorkspaceLock` + `parse_dossier` | Pass: 15 capabilities, 2 chronology, 2 impact; 7 starter templates copied from package data via `importlib.resources` | 24 | 42 |
| `find_template_file` + `load_template` (devops-senior-mgr) + `parse_job_description` + `run_match` | Pass: G-Force 70.2, WARNING, 7 gaps | 76 | 81 |
| `export_bundle` DOCX | Pass: 37,805 bytes; the owner opened it and it looks right | 105 | 851 (includes the import) |
| `export_bundle` PDF | Pass: 3,994 bytes; the owner opened it and it looks right | 17 | 17 |
| `save_vault` at 1,000,000 iterations | Pass, file mode 0o600, format 2 | 704 | 697 |
| `load_vault`, round trip equal | Pass | 661 | 656 |
| `load_vault` on the format 1 fixture (390,000 iterations) | Pass, contents as documented | 257 | 256 |

**Same answers as native CPython 3.14 on the same fixtures:** the same
counts, G-Force 70.2, alert level, gaps, and the same PBKDF2 key.

Platform probes (Pyodide on Emscripten):

| Feature | Result | Does the core need it? |
|---|---|---|
| `threading.Thread.start()` | Fails: `RuntimeError: can't start new thread` | No |
| `subprocess.run` | Fails: `OSError: [Errno 138] emscripten does not support processes` | No |
| `mkstemp`, `fchmod`, `fsync`, `os.replace`, fsync on a directory | Work on the in-memory filesystem | Yes (vault atomic write); it works unchanged |
| `os.open(O_CREAT \| O_EXCL)` lock file | Works | `WorkspaceLock`; harmless, but meaningless in a tab |
| Paths (`Path.home()` is `/home/pyodide`) | Work | All core I/O is path-based; it runs on the in-memory filesystem |
| Sockets and blocking HTTP (`urllib.request`, httpx) | Not tried | Yes, for AI calls; see point 7 and the core changes |

The in-memory filesystem is lost when the tab closes. Keeping data needs a
browser store: the File System Access API, OPFS or IndexedDB (point 6).

## 4. Measurements

**Download size**, measured from the staged files. The local server doesn't
compress; the gzip figures are compressed at level 6.

| | Uncompressed | gzip |
|---|---|---|
| Total for `core.html` (28 files) | **21.7 MB** | **14.4 MB** |
| `pyodide.asm.wasm` | 9.6 MB | 3.6 MB |
| `python_stdlib.zip` | 2.5 MB | 2.5 MB |
| cryptography | 2.2 MB | 2.1 MB |
| lxml | 2.2 MB | 2.1 MB |
| reportlab | 2.0 MB | 1.9 MB |
| Pillow | 1.0 MB | 1.0 MB |
| everything else | 2.3 MB | 1.2 MB |

Wheels and zips are already compressed, so most of the gzip saving comes
from the wasm file. Whether GitHub Pages gzips `application/wasm` isn't
verified here.

**Bytes transferred, measured in Chrome** (`PerformanceResourceTiming`,
27 requests):

- Self-hosted, first load: 21.7 MB, matching the uncompressed total
  (`serve.py` doesn't compress).
- jsDelivr, first load: **14.4 MB**, matching the gzip estimate.
  jsDelivr compresses the wasm from 9.6 MB to 3.4 MB.
- Cached reload: jsDelivr transferred **0 bytes**, with all 27 files from
  the cache. Self-hosted re-downloaded `pyodide.asm.wasm` (9.6 MB) in full
  every time and revalidated the rest. That's most likely because
  `serve.py`, like `python -m http.server`, sends no `Cache-Control`
  header; jsDelivr and GitHub Pages both send one. Treat the jsDelivr
  reload as the realistic cached figure.

**Times in Chrome 156**, from the owner's "Copy JSON" reports.

- "Usable" is the sum of loading the runtime, loading the packages,
  installing the wheels and importing the core; after that, the app could
  start working.
- "All steps" is `readyAtMs`, measured from navigation start. It includes
  the test steps, about 2.4 s of which is the vault and KDF comparison.

| Run | Usable (ms) | All steps (ms) | Transferred |
|---|---|---|---|
| Self-hosted, first load (median of 3: 6,616 / 6,632 / 6,637) | **3,068** | **6,632** | 21.7 MB |
| Self-hosted, cached reload (median of 3: 6,501 / 6,517 / 8,922) | 3,009 | 6,517 | 9.6 MB (see above) |
| jsDelivr, first load (1 run) | 5,295 | 8,888 | 14.4 MB |
| jsDelivr, cached reload (1 run) | 2,828 | 6,327 | 0 |

The self-hosted runs come from 127.0.0.1, where the download is
effectively instant. They measure the CPU cost of starting up (about 3 s),
not the network. Over the owner's real connection, the jsDelivr first load
took about 2.3 s longer. For other connections, the 14.4 MB compressed
download alone takes roughly:

| Connection | Download time |
|---|---|
| 10 Mbit/s | 12 s |
| 25 Mbit/s | 5 s |
| 50 Mbit/s | 2.3 s |
| 100 Mbit/s | 1.2 s |

**Other browsers**, one self-hosted first load each (all 13 steps passed,
21.7 MB transferred, the same answers as Chrome):

| Browser | Runtime | Packages | Install | Core import | Usable | All steps |
|---|---|---|---|---|---|---|
| Chrome 156 (median of 3) | 1,465 | 349 | 442 | 812 | 3,068 | 6,632 |
| Safari 27.2 | 1,613 | 325 | 443 | 696 | 3,077 | 7,119 |
| Firefox 150 | 1,696 | 501 | 535 | 1,028 | 3,760 | 7,607 |

All times are in ms. Safari became usable as fast as Chrome overall (its runtime
started slower, but the core imported faster); Firefox took about 23%
longer. No cached reloads
were measured in Safari or Firefox.

**The page freezes for about 1.4 s while the runtime starts and 0.8 s while
the core imports**, on every load. A Web Worker would keep the page
responsive during startup.

**Node smoke run, for reference only** (Node 26.12, Apple silicon, local
files): runtime 1,575 ms, packages 360 ms, micropip install 458 ms.

### Key derivation: Pyodide versus WebCrypto

PBKDF2-HMAC-SHA256, 1,000,000 iterations, same passphrase and salt, 32-byte
key:

| | Time (ms) | Key |
|---|---|---|
| Native CPython 3.14 + cryptography 50.0.2 | 153 | `a0b9a7a9…ebebb5` |
| Pyodide cryptography 47.0.0 (Node) | 655 | identical |
| WebCrypto `crypto.subtle.deriveBits` (Node) | 166 | identical |
| **Pyodide cryptography (Chrome 156)** | **660** (page frozen 660 ms) | identical |
| **WebCrypto `deriveBits` (Chrome 156)** | **129** (no freeze; the longest gap was 26 ms) | identical |
| Pyodide cryptography (Safari 27.2 / Firefox 150, 1 run each) | 730 / 715 | identical |
| WebCrypto `deriveBits` (Safari 27.2 / Firefox 150, 1 run each) | 235 / 177 | identical |

Chrome numbers are the median of the three first loads; all eight Chrome
runs fell between 658 and 668 ms for Pyodide and were exactly 129 ms for
WebCrypto. **In Chrome, WebCrypto is about 5× faster than Pyodide's
cryptography build**, slightly faster than native CPython, and derives the
same bytes. WebCrypto was also 3–4× faster in Safari and Firefox.

The Pyodide derivation also blocks the page: a vault save followed by a
load froze it for 1.6 s. WebCrypto runs off the main thread. So the browser
build should derive the key with WebCrypto (core change 3); the vault
format doesn't change.

## 5. Content Security Policy

The test page is served by `serve.py` with this header:

```
default-src 'none'; script-src 'self' 'wasm-unsafe-eval';
connect-src 'self' https://api.anthropic.com https://api.openai.com https://generativelanguage.googleapis.com;
style-src 'self'; img-src 'self' blob: data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
```

**Expected minimum for Pyodide: `script-src 'self' 'wasm-unsafe-eval'` and
`connect-src 'self'`.** `'unsafe-eval'` shouldn't be needed. This is
expected from reading the code; the browser run confirms it.

- `pyodide.mjs` and `pyodide.asm.mjs` contain no `new Function`. The
  `eval()` calls in `pyodide.asm.mjs` are Emscripten's:
  - turning EM_ASM/EM_JS code into functions when a side module that has
    such code is loaded
  - `emscripten_run_script`
  - a Node-only path.
- None of the 16 `.so` files in the packages loaded here (cffi,
  cryptography, lxml, Pillow, PyYAML) contain EM_ASM or EM_JS sections, so
  those eval paths shouldn't run.
- Compiling wasm needs `'wasm-unsafe-eval'`.
- Package wheels and the stdlib come in through `fetch`, which needs
  `connect-src 'self'`.
- The `blob:` URLs used for downloads need no directive.
- Not needed by this page: `worker-src`, since Pyodide runs on the main
  thread here. A Web Worker build would add `worker-src 'self'`.
- `--csp eval` is there to confirm `'unsafe-eval'` as the cause if the
  strict run shows eval violations.
- The page records every `securitypolicyviolation` event in its report.

**Confirmed in Chrome 156:** with the strict policy above, all six
self-hosted runs passed every step and recorded **zero CSP violations**.
`'unsafe-eval'` isn't needed, and `--csp eval` wasn't used. The two jsDelivr
runs also recorded zero violations under the `cdn` variant.

The smallest set Pyodide itself needs:

```
script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'
```

`'wasm-unsafe-eval'` is required for WebAssembly. The rest of the strict
policy is defence in depth, plus the AI hosts in `connect-src` for later.
One first load each in Safari 27.2 and Firefox 150 also passed every step with zero violations under the same strict policy. The files page ran in both under the strict CSP too.

The CDN variant adds `https://cdn.jsdelivr.net` to `script-src` and
`connect-src`. The probe variant adds `https://pypi.org` and
`https://files.pythonhosted.org` to `connect-src`.

## 6. Files in the browser

[`files.html`](../../spikes/browser-pyodide/files.html) tests:

- **(a)** `showDirectoryPicker()`: list, read, and write `qv-test.txt`
  back
- **(b)** the fallback: `<input type=file multiple>`,
  `<input webkitdirectory>`, and a download through a Blob link.

The steps are in the
[spike README](../../spikes/browser-pyodide/README.md#files-page-by-hand-point-6).

Owner's results, 28 Oct 2026, macOS, server in strict-CSP mode, using a
copy of the synthetic fixtures folder:

| | Chrome 156.0.8078.48 | Safari 27.2 | Firefox 150.0.1 |
|---|---|---|---|
| (a) Open a folder (`showDirectoryPicker`) | **Works.** Listed the 3 `.md` files and read them. | Not supported | Not supported |
| (a) Write a file back into the folder | **Works.** Wrote `qv-test.txt` and read it back. | Not supported | Not supported |
| `showOpenFilePicker` / `showSaveFilePicker` | Yes | No | No |
| (b) Choose files | Works (3 files) | Works (3 files) | Works (3 files) |
| (b) Choose a folder (read only) | Works; also included `.DS_Store` | Works; hidden files left out | Works; also included `.DS_Store` |
| (b) Download through a Blob link | Started | Started | Started |
| OPFS (browser-private storage) | Yes | Yes | Yes |
| Secure context on 127.0.0.1 | Yes | Yes | Yes |
| Confusing prompts | None reported | None reported | None reported |

These match the expected support. The page logged that each download
started, but the owner didn't separately report checking that it arrived
in Downloads.

Two details for a real build:

- When choosing a folder, Chrome and Firefox include hidden files such as
  `.DS_Store`, so the app has to filter them.
- In Chrome, cancelling a picker fires an empty selection ("0 file(s)
  chosen"), which the app should ignore.

The spike page's support table showed two labels as HTML, so the
`<input webkitdirectory>` row displayed an empty box. That bug was in the
spike page only and is fixed; it didn't affect the results.

What this means: only Chromium browsers can work on a real folder of
Markdown files in place. Safari and Firefox users would upload their files,
keep them in browser-private storage, and download changes. In that model,
the browser holds the only copy until the user downloads one.

## 7. AI calls from the browser

From official sources only: the providers' docs and their official SDK
repositories. No API calls were made; live testing waits for backlog
item 8.

| Provider | Direct browser calls | What it needs | Official position |
|---|---|---|---|
| Anthropic | Supported, opt-in | Request header `anthropic-dangerous-direct-browser-access: true`. The official TypeScript SDK sends it when `dangerouslyAllowBrowser: true` is set ([`src/client.ts`](https://github.com/anthropics/anthropic-sdk-typescript/blob/main/src/client.ts)). | The SDK README says browser use is "disabled by default to avoid exposing your secret API credentials" ([README](https://github.com/anthropics/anthropic-sdk-typescript)). The API docs pages found don't describe the header in prose. |
| OpenAI | The SDK allows it with `dangerouslyAllowBrowser: true` | No extra header is documented. | The SDK README says it "exposes your secret API credentials in the client-side code". It names trusted internal tools and short-lived keys as the acceptable cases ([README](https://github.com/openai/openai-node)). The official docs found don't state the API's CORS behaviour. |
| Google Gemini | The SDK supports it ("In the browser the initialization code is identical") | API key in header `x-goog-api-key`. | "Avoid exposing API keys in client-side code. Use server-side implementations in production" ([js-genai README](https://github.com/googleapis/js-genai)). Also: "Do not hardcode API keys directly in web or mobile apps … run a backend proxy server" ([API key docs](https://ai.google.dev/gemini-api/docs/api-key)). |

All three can be called from a page, but all three officially discourage
putting a key in the browser. For QuestVector the key would be the user's
own key, typed in by the user and kept in their own encrypted vault (bring
your own key). That's closer to the "trusted user" case the docs allow, but
an XSS bug would expose the key, so the strict CSP matters.

What the official docs don't settle, and backlog item 8 should check live:

- whether OpenAI's endpoint returns CORS headers for any origin
- whether an Anthropic organisation setting can block browser access.

## What would need changing in the core

1. **Make pywebview optional** (for example a `desktop` extra). Today it's
   a hard dependency, so a normal `micropip.install` fails on
   proxy-tools. This touches `pyproject.toml`, the install docs, and how
   `qv` starts the desktop app. It needs an ADR.
2. **A browser transport for AI.** Each provider's `generate()` is
   synchronous, and goes through the vendor's Python SDK (httpx) or, for
   Ollama, `urllib.request`. Neither works in a browser tab: there are no
   sockets, and the main thread can't block on HTTP. Options:
   - an async provider path that calls JavaScript `fetch` through Pyodide,
     added through the registry in `questvector/core/llm.py`
   - prompt building in Python and the call made in JavaScript.

   Ollama from a page also needs `OLLAMA_ORIGINS` set by the user.
3. **Derive the vault key with WebCrypto.** In Chrome, WebCrypto took
   129 ms and Pyodide's cryptography took 660 ms for the same key, and
   Pyodide's froze the page for that long. The vault would accept an
   injected key-derivation
   function, while AES-GCM and the file format stay as they are, so a vault
   moves between desktop and browser unchanged.
4. **Bytes in, bytes out.** The core's path-based API works on Pyodide's
   in-memory filesystem, so no change is strictly needed. Small
   bytes-returning variants of `export_bundle` and the vault functions would
   save copying files in and out of that filesystem.
5. **A browser storage adapter** (outside the core): the File System Access
   API on Chromium; OPFS or IndexedDB plus upload/download elsewhere.
6. **Test on Pyodide's package versions.** Pyodide ships cryptography 47,
   cffi 2.0 and Pillow 12.2, against 50, 2.1 and 13 in the lock. A browser
   build would need its own CI job running the suite under Pyodide (for
   example with `pytest-pyodide`). That's a new required check (ADR-0011).

Nothing in `exporter.py`, `matcher.py`, `markdown_parser.py` or
`templates.py` needed changing.

## Risks

- **First-load size and startup.** 14.4 MB compressed before the app does
  anything, much more than a typical web page. That's about 12 s of
  download at 10 Mbit/s, plus about 3 s of startup on an Apple-silicon Mac.
  Older laptops and phones would start more slowly. Not measured:
  mobile or slower CPUs (Safari and Firefox on the same Mac were
  similar). Cached reloads skip the download but
  not the startup. Loading the export
  libraries (reportlab, python-docx, lxml, Pillow) only at export time
  would save about 5.4 MB on first load.
- **Browser storage can be evicted.** Data in OPFS or IndexedDB can be
  cleared by the browser, and by the user clearing site data. Safari can
  also clear script-written storage for a site that isn't visited for a
  while. For career data, a browser-only app needs
  `navigator.storage.persist()`, clear "download a backup" prompts, and
  shouldn't present browser storage as safe storage.
- **Safari and Firefox gaps.** They have no folder access (point 6), so
  they get a worse experience and the copy in the browser can drift from
  the user's files.
- **API keys in a browser.** All three providers discourage it (point 7).
  Mitigations: bring-your-own-key only, the vault encrypted with the
  user's passphrase, the strict CSP, and no third-party scripts.
- **Supply chain.**
  - Self-hosting pinned, hash-checked files removes the run-time CDN
    dependency. The site then serves about 22 MB of third-party binaries
    that would need the same review discipline as `uv.lock`: Dependabot
    doesn't track Pyodide pins.
  - Subresource Integrity can't cover Pyodide's dynamic `import()` and
    `fetch` of wheels.
- **ADR-0001.** Serving the app from GitHub Pages is hosting, even if no
  data leaves the browser. This needs a new ADR narrowing ADR-0001, and the
  README, spec and PRD non-goals updated, as backlog item 14 notes for
  AWS.
- **Two runtimes to support.** Desktop on CPython and browser on Pyodide,
  with different dependency versions and a Pyodide release cadence to
  track. The main release line moving to Python-numbered versions (314.x)
  should help keep them aligned.
- **Freezes on the main thread.** Measured in Chrome:
  - about 1.4 s while the runtime starts and 0.8 s while the core imports,
    on every load
  - 0.66 s for each wasm key derivation.

  WebCrypto fixes the key derivation (change 3); running Pyodide in a Web
  Worker would fix startup (`worker-src 'self'` in the CSP).

## Recommendation

**Go with changes.**

- The core works unchanged in Chrome, Safari and Firefox on synthetic data,
  and its answers are identical to native.
- It holds a strict CSP without `'unsafe-eval'`.
- Every blocker found has a contained fix (changes 1–3).
- On the owner's Mac, it's usable about 3 s after the files arrive in
  Chrome and Safari, and 3.8 s in Firefox.

What could still turn this into a **stop**, and needs checking before
building:

- **Cold load on the target users' devices and connections.** About 14 MB
  plus startup is fine on broadband and a recent laptop. It hasn't been
  measured on phones, older machines, or slow connections.
- **Browser storage as the only copy of career data** (eviction, point 6).
  If the target users are mostly on Safari, they get no folder access.
  Their data would then live in browser storage, backed up by downloads,
  which is a weaker promise than the desktop app's plain files.

## Open questions

1. Who are the target users' browsers? If most are on Safari (iPhone or
   Mac), the browser app is the upload/download model, not the folder
   model.
2. Is about 14 MB gzipped on first visit acceptable? Should export
   libraries load only when used?
3. Is AI in the browser in scope for the first browser version, or does it
   ship with parsing, matching and export only, with AI added after
   backlog item 8?
4. Should a browser build share vault files with the desktop app (same
   format, WebCrypto KDF), or have its own store?
5. Does GitHub Pages compress `application/wasm`? Check when hosting is
   decided (ADR-0001 successor).
6. Would a Pyodide CI job (a new required check under ADR-0011) be
   acceptable, or should the browser build stay best-effort and untested in
   CI?
