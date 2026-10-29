// Headless smoke run of the spike's Python steps in Node, against a staged folder.
// Spike code only: it checks steps.py works before the browser runs. Its
// timings are Node's, not a browser's, and the write-up labels them so.
//
// Usage: node spikes/browser-pyodide/smoke.mjs SERVE_DIR

import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const root = path.resolve(process.argv[2]);
const { loadPyodide } = await import(pathToFileURL(path.join(root, "pyodide", "pyodide.mjs")).href);
const PACKAGES = ["micropip", "cryptography", "lxml", "pyyaml", "pillow", "charset-normalizer", "typing-extensions"];
const results = [];

async function timed(name, fn) {
  const start = performance.now();
  let out;
  try {
    out = await fn();
    if (!(out && typeof out === "object" && "ok" in out)) out = { ok: true, data: out ?? null };
  } catch (error) {
    out = { ok: false, error: String(error?.stack ?? error) };
  }
  out.ms = Math.round(performance.now() - start);
  results.push({ name, ...out });
  console.log(`${out.ok ? "pass" : "FAIL"}  ${String(out.ms).padStart(6)} ms  ${name}  ${JSON.stringify(out.ok ? out.data : out.error)}`);
  if (!out.ok && out.traceback) console.log(out.traceback);
  return out;
}

let pyodide;
await timed("load Pyodide runtime", async () => {
  pyodide = await loadPyodide({ indexURL: path.join(root, "pyodide") + path.sep });
  return pyodide.runPython("import sys; sys.version");
});
await timed("load Pyodide packages", () => pyodide.loadPackage(PACKAGES, { messageCallback: () => {} }));

pyodide.FS.mkdirTree("/home/pyodide/fixtures");
for (const name of await readdir(path.join(root, "fixtures"))) {
  pyodide.FS.writeFile(`/home/pyodide/fixtures/${name}`, await readFile(path.join(root, "fixtures", name)));
}
pyodide.FS.mkdirTree("/home/pyodide/wheels");
const wheelUrls = [];
for (const name of await readdir(path.join(root, "wheels"))) {
  pyodide.FS.writeFile(`/home/pyodide/wheels/${name}`, await readFile(path.join(root, "wheels", name)));
  wheelUrls.push(`emfs:/home/pyodide/wheels/${name}`);
}
pyodide.FS.writeFile("/home/pyodide/steps.py", await readFile(path.join(root, "steps.py"), "utf8"));
pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
const steps = pyodide.pyimport("steps");
const py = (name, ...args) => JSON.parse(steps.run(name, ...args));
const pyAsync = async (name, ...args) => JSON.parse(await steps.run_async(name, ...args));

await timed("install wheels (micropip, local only)", () => pyAsync("install", pyodide.toPy(wheelUrls)));
await timed("platform probes", () => py("probe_platform"));
await timed("parse dossier", () => py("step_parse"));
await timed("match", () => py("step_match"));
await timed("export DOCX", () => py("step_export", "docx"));
await timed("export PDF", () => py("step_export", "pdf"));
await timed("vault save/load + v1 fixture", () => py("step_vault"));
const pyKdf = await timed("PBKDF2 1M: Pyodide cryptography", () => py("step_kdf"));
const webKdf = await timed("PBKDF2 1M: WebCrypto (Node)", async () => {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode("qv-spike-passphrase"), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt: enc.encode("qv-spike-salt-16"), iterations: 1_000_000 }, key, 256);
  return { key_hex: Buffer.from(bits).toString("hex") };
});
console.log(`KDF keys match: ${pyKdf.ok && webKdf.ok && pyKdf.data.key_hex === webKdf.data.key_hex}`);
console.log(`${results.filter((r) => !r.ok).length} failed of ${results.length}`);
