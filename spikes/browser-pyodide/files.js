// Files test page for the browser/Pyodide spike. Spike code only.
// A: the File System Access API (open a folder, read, write back).
// B: the fallback every browser has (file inputs to read, a Blob link to save).

const $ = (id) => document.getElementById(id);
const testText = () => `QuestVector spike write test\n${new Date().toISOString()}\n${navigator.userAgent}\n`;

const support = {
  "showDirectoryPicker (open a folder, read and write)": "showDirectoryPicker" in window,
  "showOpenFilePicker": "showOpenFilePicker" in window,
  "showSaveFilePicker": "showSaveFilePicker" in window,
  "OPFS (navigator.storage.getDirectory)": Boolean(navigator.storage?.getDirectory),
  "<input webkitdirectory> (choose a folder, read only)": "webkitdirectory" in document.createElement("input"),
  "<a download> (save a file)": "download" in document.createElement("a"),
  "Secure context": window.isSecureContext,
};
for (const [name, ok] of Object.entries(support)) {
  const row = $("support").insertRow();
  row.insertCell().textContent = name; // text, not HTML: two labels contain tag names
  Object.assign(row.insertCell(), { textContent: ok ? "yes" : "no", className: ok ? "yes" : "no" });
}

function log(id, line) {
  const el = $(id);
  el.textContent = (el.textContent === "Not started." ? "" : el.textContent + "\n") + line;
}

async function describe(file) {
  const text = await file.text();
  return `${file.webkitRelativePath || file.name}: ${file.size} bytes, first line "${text.split("\n")[0].slice(0, 60)}"`;
}

// A. File System Access API
let folder = null;
$("pick-folder").addEventListener("click", async () => {
  if (!("showDirectoryPicker" in window)) {
    log("folder-log", "Not supported in this browser: use section B.");
    return;
  }
  try {
    folder = await window.showDirectoryPicker({ mode: "readwrite" });
  } catch (error) {
    log("folder-log", `Cancelled or refused: ${error.name}: ${error.message}`);
    return;
  }
  log("folder-log", `Opened folder "${folder.name}".`);
  for await (const [name, handle] of folder.entries()) {
    if (handle.kind === "file" && /\.(md|txt|json)$/i.test(name)) {
      log("folder-log", "  " + (await describe(await handle.getFile())));
    } else {
      log("folder-log", `  ${name} (${handle.kind}, skipped)`);
    }
  }
  $("write-back").disabled = false;
});

$("write-back").addEventListener("click", async () => {
  try {
    const permission = await folder.requestPermission({ mode: "readwrite" });
    if (permission !== "granted") throw new Error(`permission ${permission}`);
    const handle = await folder.getFileHandle("qv-test.txt", { create: true });
    const writable = await handle.createWritable();
    await writable.write(testText());
    await writable.close();
    const check = await (await handle.getFile()).text();
    log("folder-log", `Wrote qv-test.txt (${check.length} bytes) and read it back: ${check.startsWith("QuestVector") ? "matches" : "DIFFERENT"}.`);
  } catch (error) {
    log("folder-log", `Write failed: ${error.name}: ${error.message}`);
  }
});

// B. Fallback
async function listFiles(event) {
  const files = [...event.target.files];
  log("upload-log", `${files.length} file(s) chosen:`);
  for (const file of files) log("upload-log", "  " + (await describe(file)));
}
$("pick-files").addEventListener("change", listFiles);
$("pick-dir").addEventListener("change", listFiles);

$("download").addEventListener("click", () => {
  const url = URL.createObjectURL(new Blob([testText()], { type: "text/plain" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: "qv-test.txt" });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  log("upload-log", "Started a download of qv-test.txt: check the browser's downloads.");
});
