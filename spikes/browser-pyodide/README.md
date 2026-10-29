# Browser/Pyodide spike: prototype

Time-boxed experiment, not a feature. Findings:
[`docs/spikes/2026-10-browser-pyodide.md`](../../docs/spikes/2026-10-browser-pyodide.md).
Nothing here is imported by `questvector/` or run by the test suite or CI.
Everything runs on 127.0.0.1 with synthetic fixtures only.

| File | What it is |
|---|---|
| `stage.py` | Downloads Pyodide 314.0.7 and the wheels the core needs, checks every hash, and assembles a folder to serve. The only step that uses the network; the page itself loads nothing from outside 127.0.0.1 unless you use `?cdn`. |
| `serve.py` | Local static server that adds a Content Security Policy header (`--csp strict\|eval\|cdn\|probe\|none`). |
| `core.html`, `core.js` | Loads Pyodide, installs the questvector wheel, runs the steps, times them, and offers DOCX/PDF downloads and "Copy JSON". |
| `steps.py` | The Python steps, calling the unmodified core. |
| `files.html`, `files.js` | File System Access API and upload/download fallback test. |
| `smoke.mjs` | Runs `steps.py` headless in Node, to check the steps before a browser run. Node timings aren't browser timings. |

## Run it

From the repo root, with a scratch folder outside the repo (`SCRATCH` below):

```bash
uv build --wheel --out-dir "$SCRATCH/dist"
uv run python spikes/browser-pyodide/stage.py --wheel "$SCRATCH"/dist/questvector-*.whl --out "$SCRATCH/serve"
node spikes/browser-pyodide/smoke.mjs "$SCRATCH/serve"          # optional headless check
uv run python spikes/browser-pyodide/serve.py "$SCRATCH/serve"  # strict CSP, http://127.0.0.1:8765/
```

The built wheel, the downloads, and the served folder stay in `$SCRATCH` and
are never committed.

## Measuring in Chrome (point 4)

Use a fresh Chrome profile or a Guest window so extensions don't skew the
numbers. Keep DevTools closed while timing, except where noted.

1. **First load:** open DevTools → Application → Storage → "Clear site
   data" for `127.0.0.1:8765`, close DevTools, then open
   `http://127.0.0.1:8765/core.html`. Wait for "Done", click **Copy JSON**,
   and paste it into the conversation labelled "cold 1". Repeat twice more
   (clear site data each time) for "cold 2" and "cold 3".
2. **Cached reload:** without clearing anything, reload the page (Cmd-R,
   not Shift-Cmd-R). Copy JSON as "warm 1". Repeat twice more.
3. **CDN, secondary:** stop the server, restart it with `--csp cdn`, open
   `core.html?cdn`, and do one cold and one warm run.
4. **Dependency probe:** restart with `--csp probe`, open
   `core.html?probe`, and copy one run. This is the only page that contacts
   PyPI.
5. **CSP:** each JSON includes `cspViolations`. If the strict run fails with
   eval violations, restart with `--csp eval` and run once more to confirm
   that `'unsafe-eval'` is the cause.
6. Open the downloaded DOCX in Word or Pages and the PDF in Preview, and
   say whether they look right.

## Files page by hand (point 6)

Make a scratch folder holding copies of `tests/fixtures/ollama_live/*.md`
(synthetic). With the server running, open
`http://127.0.0.1:8765/files.html` in each browser. The "What this browser
supports" table is filled in automatically.

**A. Open a folder:**
1. Click **Open folder…**, choose the scratch folder, and allow access.
   Expected: the log lists the `.md` files with sizes and first lines.
2. Click **Write qv-test.txt into the folder** and allow editing. Expected:
   "Wrote qv-test.txt … matches", and the file appears in Finder.

Expected by browser: Chrome works. Safari and Firefox say "Not supported in
this browser"; that is the finding, not a bug.

**B. Upload and download:**
1. Click **Choose files…** and pick the three `.md` files. Expected: all
   three are listed.
2. Click **Choose a folder…** and pick the scratch folder. Expected: the
   files are listed with their folder path. The browser may ask you to
   confirm the upload; nothing leaves the machine.
3. Click **Download qv-test.txt**. Expected: the file lands in Downloads.

For each browser, note the version (from its About menu), each step's
result, and any prompts that would confuse a less-technical user.
