// Core test page for the browser/Pyodide spike. Spike code only.
//
// Loads the pinned Pyodide, installs the questvector wheel from local files,
// runs the unmodified core on the synthetic fixtures (steps.py), times every
// step, and builds a JSON report for "Copy JSON".
//
// Query flags: ?cdn     load Pyodide from jsDelivr (pinned) instead of /pyodide/
//              ?probe   also try a normal micropip install that resolves
//                       dependencies from PyPI (needs serve.py --csp probe)

const PYODIDE_VERSION = "314.0.7";
const PACKAGES = ["micropip", "cryptography", "lxml", "pyyaml", "pillow", "charset-normalizer", "typing-extensions"];
const FIXTURES = ["Capabilities.md", "Chronology.md", "Impact.md", "job_description.txt", "v1-vault.json"];
const KDF = { passphrase: "qv-spike-passphrase", salt: "qv-spike-salt-16", iterations: 1_000_000 };

const params = new URLSearchParams(location.search);
const useCdn = params.has("cdn");
const runProbe = params.has("probe");
const indexURL = useCdn
  ? `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`
  : new URL("pyodide/", location.href).href;

const report = {
  spike: "browser-pyodide",
  pyodide: PYODIDE_VERSION,
  mode: useCdn ? "cdn" : "self-hosted",
  userAgent: navigator.userAgent,
  startedAt: new Date().toISOString(),
  navigationType: performance.getEntriesByType("navigation")[0]?.type ?? "unknown",
  steps: [],
  cspViolations: [],
};

document.addEventListener("securitypolicyviolation", (event) => {
  report.cspViolations.push({
    directive: event.violatedDirective,
    blocked: event.blockedURI,
    sample: event.sample,
    source: `${event.sourceFile}:${event.lineNumber}`,
  });
  render();
});
performance.setResourceTimingBufferSize(1000);

// A heartbeat every 25 ms; the longest gap during a step is how long the
// page was frozen by it (the main thread can't paint or respond meanwhile).
let lastBeat = performance.now();
let longestGap = 0;
setInterval(() => {
  const now = performance.now();
  longestGap = Math.max(longestGap, now - lastBeat);
  lastBeat = now;
}, 25);
const yieldToBrowser = () => new Promise((resolve) => setTimeout(resolve, 30));

const $ = (id) => document.getElementById(id);

function render() {
  const rows = report.steps
    .map((s) => `<tr class="${s.ok ? "ok" : "fail"}"><td>${s.name}</td><td>${s.ok ? "pass" : "FAIL"}</td>` +
      `<td class="num">${s.ms}</td><td class="num">${s.frozenMs}</td><td><code>${escapeHtml(summary(s))}</code></td></tr>`)
    .join("");
  $("steps").innerHTML = rows;
  $("report").textContent = JSON.stringify(report, null, 2);
}

function summary(step) {
  return step.ok ? JSON.stringify(step.data) : step.error;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

// Runs one step, records its time and outcome, and never throws.
async function timed(name, fn) {
  await yieldToBrowser();
  longestGap = 0;
  lastBeat = performance.now();
  const start = performance.now();
  const step = { name };
  try {
    const result = await fn();
    // Python steps return {"ok", "data"|"error", "traceback"} (steps.run).
    if (result && typeof result === "object" && "ok" in result) Object.assign(step, result);
    else Object.assign(step, { ok: true, data: result ?? null });
  } catch (error) {
    Object.assign(step, { ok: false, error: String(error), traceback: error?.stack });
  }
  step.ms = Math.round(performance.now() - start);
  await yieldToBrowser();
  step.frozenMs = Math.round(longestGap);
  report.steps.push(step);
  render();
  return step;
}

function resourceTotals() {
  const entries = performance.getEntriesByType("resource");
  const sum = (key) => entries.reduce((total, e) => total + (e[key] || 0), 0);
  const largest = [...entries]
    .sort((a, b) => b.decodedBodySize - a.decodedBodySize)
    .slice(0, 8)
    .map((e) => ({ url: e.name.replace(location.origin, ""), transfer: e.transferSize, decoded: e.decodedBodySize }));
  return {
    requests: entries.length,
    transferBytes: sum("transferSize"),
    encodedBytes: sum("encodedBodySize"),
    decodedBytes: sum("decodedBodySize"),
    servedFromCache: entries.filter((e) => e.transferSize === 0 && e.decodedBodySize > 0).length,
    largest,
  };
}

function offerDownload(pyodide, path, label, mime) {
  const bytes = pyodide.FS.readFile(path);
  const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
  const link = document.createElement("a");
  link.href = url;
  link.download = path.split("/").pop();
  link.textContent = `Download ${label} (${bytes.length.toLocaleString()} bytes)`;
  link.className = "button";
  $("downloads").append(link);
}

async function webCryptoKdf() {
  const enc = new TextEncoder();
  const start = performance.now();
  const key = await crypto.subtle.importKey("raw", enc.encode(KDF.passphrase), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt: enc.encode(KDF.salt), iterations: KDF.iterations },
    key,
    256,
  );
  const ms = Math.round(performance.now() - start);
  const keyHex = [...new Uint8Array(bits)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return { ms, key_hex: keyHex };
}

async function main() {
  $("mode").textContent = `${report.mode} · Pyodide ${PYODIDE_VERSION}`;
  const manifest = await (await fetch("manifest.json")).json();
  const wheelUrls = manifest.wheels.map((name) => new URL(`wheels/${name}`, location.href).href);
  const qvWheel = wheelUrls.find((url) => url.includes("questvector-"));

  let pyodide;
  const loaded = await timed("load Pyodide runtime", async () => {
    const { loadPyodide } = await import(indexURL + "pyodide.mjs");
    pyodide = await loadPyodide({ indexURL });
    return { python: pyodide.runPython("import sys; sys.version") };
  });
  if (!loaded.ok) return finish();

  const packages = await timed("load Pyodide packages", async () => {
    await pyodide.loadPackage(PACKAGES, { messageCallback: () => {} });
    return { requested: PACKAGES };
  });
  if (!packages.ok) return finish();

  await timed("stage fixtures and steps.py", async () => {
    pyodide.FS.mkdirTree("/home/pyodide/fixtures");
    for (const name of FIXTURES) {
      const bytes = new Uint8Array(await (await fetch(`fixtures/${name}`)).arrayBuffer());
      pyodide.FS.writeFile(`/home/pyodide/fixtures/${name}`, bytes);
    }
    pyodide.FS.writeFile("/home/pyodide/steps.py", await (await fetch("steps.py")).text());
    pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
    return { fixtures: FIXTURES.length };
  });
  const steps = pyodide.pyimport("steps");
  const py = (name, ...args) => JSON.parse(steps.run(name, ...args));
  const pyAsync = async (name, ...args) => JSON.parse(await steps.run_async(name, ...args));

  if (runProbe) {
    await timed("probe: micropip install with PyPI dependencies", () => pyAsync("probe_full_install", qvWheel));
  }
  const installed = await timed("install wheels (micropip, local only)", () =>
    pyAsync("install", pyodide.toPy(wheelUrls)));
  await timed("platform probes", () => py("probe_platform"));
  if (!installed.ok) return finish();

  await timed("import questvector core", () => {
    pyodide.runPython("import questvector.core.exporter, questvector.core.vault, questvector.core.matcher");
    return null;
  });
  const parsed = await timed("parse dossier", () => py("step_parse"));
  const matched = parsed.ok && (await timed("match (template + job description)", () => py("step_match")));
  if (matched?.ok) {
    const docx = await timed("export DOCX", () => py("step_export", "docx"));
    if (docx.ok) offerDownload(pyodide, docx.data.path, "DOCX",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
    const pdf = await timed("export PDF", () => py("step_export", "pdf"));
    if (pdf.ok) offerDownload(pyodide, pdf.data.path, "PDF", "application/pdf");
  }
  await timed("vault save/load (1M iterations) + v1 fixture", () => py("step_vault"));
  const pyKdf = await timed("PBKDF2 1M: Pyodide cryptography", () => py("step_kdf"));
  const webKdf = await timed("PBKDF2 1M: WebCrypto deriveBits", webCryptoKdf);
  report.kdfKeysMatch = pyKdf.ok && webKdf.ok ? pyKdf.data.key_hex === webKdf.data.key_hex : null;
  finish();
}

function finish() {
  report.readyAtMs = Math.round(performance.now()); // since navigation start
  report.resources = resourceTotals();
  report.passed = report.steps.filter((s) => s.ok).length;
  report.failed = report.steps.filter((s) => !s.ok).length;
  $("status").textContent = `Done: ${report.passed} passed, ${report.failed} failed, ` +
    `${report.cspViolations.length} CSP violations, ${(report.resources.transferBytes / 1e6).toFixed(1)} MB transferred.`;
  render();
}

$("copy").addEventListener("click", async () => {
  await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
  $("copy").textContent = "Copied";
});

main().catch((error) => {
  report.fatal = String(error?.stack ?? error);
  finish();
});
