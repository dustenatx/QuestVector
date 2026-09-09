// QuestVector Tactical Flight Deck — front-end logic.
// Every data call goes through window.pywebview.api (see
// questvector/desktop/app.py::Api), which always resolves to
// {ok: true, data: ...} or {ok: false, error: "..."} — never a raw
// exception — so every handler below only needs one shape to branch on.

const GAUGE_CIRCUMFERENCE = 282.6;

let apiReady = false;
let lastScan = { jdText: "", templateId: "" };

function setStatus(text, tone = "success") {
  const el = document.getElementById("status-line");
  el.textContent = text;
  el.style.color = tone === "critical" ? "var(--lock-on-red)"
    : tone === "warning" ? "var(--afterburner-amber)"
    : "var(--tactical-green)";
  el.style.borderColor = el.style.color;
}

function currentWorkspaceDir() {
  return document.getElementById("workspace-dir").value.trim();
}

function requireApi() {
  if (!apiReady || !window.pywebview) {
    setStatus("BRIDGE OFFLINE", "critical");
    throw new Error("Desktop bridge is not ready yet.");
  }
  return window.pywebview.api;
}

function renderJson(elementId, payload) {
  document.getElementById(elementId).textContent = JSON.stringify(payload, null, 2);
}

// --- Tab switching -----------------------------------------------------

document.getElementById("tabs").addEventListener("click", (event) => {
  const button = event.target.closest(".hud-tab");
  if (!button) return;
  document.querySelectorAll(".hud-tab").forEach((tab) => tab.classList.remove("active"));
  button.classList.add("active");
  document.querySelectorAll("[data-panel]").forEach((panel) => panel.classList.add("hidden"));
  document.getElementById(`panel-${button.dataset.tab}`).classList.remove("hidden");
  if (button.dataset.tab === "sync") refreshTemplates();
});

// --- Workspace -----------------------------------------------------------

document.getElementById("btn-launch").addEventListener("click", async () => {
  try {
    const api = requireApi();
    const dir = currentWorkspaceDir();
    if (!dir) return setStatus("ENTER A WORKSPACE PATH", "warning");
    const response = await api.launch_workspace(dir);
    renderJson("workspace-output", response);
    setStatus(response.ok ? "WORKSPACE READY" : "LAUNCH FAILED", response.ok ? "success" : "critical");
  } catch (err) {
    renderJson("workspace-output", { ok: false, error: String(err) });
  }
});

// --- Dossier -------------------------------------------------------------

document.getElementById("btn-load-dossier").addEventListener("click", async () => {
  const api = requireApi();
  const dir = currentWorkspaceDir();
  if (!dir) return setStatus("ENTER A WORKSPACE PATH", "warning");
  const response = await api.get_dossier(dir);
  const container = document.getElementById("dossier-output");
  container.innerHTML = "";
  if (!response.ok) {
    container.textContent = response.error;
    return;
  }
  const { capabilities, chronology, impact } = response.data;
  container.innerHTML = `
    <div><h3>Capabilities (${capabilities.length})</h3>
      <ul class="hud-list">${capabilities.map((c) => `<li><b>${c.domain}</b>: ${c.text}</li>`).join("")}</ul>
    </div>
    <div><h3>Chronology (${chronology.length})</h3>
      <ul class="hud-list">${chronology.map((e) => `<li><b>${e.heading}</b></li>`).join("")}</ul>
    </div>
    <div><h3>Impact (${impact.length})</h3>
      <ul class="hud-list">${impact.map((s) => `<li><b>${s.heading}</b></li>`).join("")}</ul>
    </div>`;
});

// --- Sync-AST / G-Force gauge ---------------------------------------------

async function refreshTemplates() {
  const api = requireApi();
  const dir = currentWorkspaceDir();
  const select = document.getElementById("template-select");
  select.innerHTML = '<option value="">Select mission template&hellip;</option>';
  if (!dir) return;
  const response = await api.list_templates(dir);
  if (!response.ok) return;
  for (const template of response.data) {
    const option = document.createElement("option");
    option.value = template.id;
    option.textContent = `${template.title} (${template.id})`;
    select.appendChild(option);
  }
}

document.getElementById("btn-refresh-templates").addEventListener("click", refreshTemplates);

function setGauge(score, alertLevel) {
  const fill = document.getElementById("gauge-fill");
  const offset = GAUGE_CIRCUMFERENCE * (1 - Math.max(0, Math.min(100, score)) / 100);
  fill.style.strokeDashoffset = String(offset);
  const colorVar = alertLevel === "critical" ? "var(--lock-on-red)"
    : alertLevel === "warning" ? "var(--afterburner-amber)"
    : "var(--tactical-green)";
  fill.style.stroke = colorVar;
  document.getElementById("gauge-readout").textContent = `${score.toFixed(1)}%`;
  document.getElementById("gauge-alert").textContent =
    alertLevel === "critical" ? "CRITICAL GAP DETECTED"
    : alertLevel === "warning" ? "GAPS DETECTED"
    : "G-FORCE MATCH LOCKED";
}

document.getElementById("btn-run-scan").addEventListener("click", async () => {
  const api = requireApi();
  const dir = currentWorkspaceDir();
  const templateId = document.getElementById("template-select").value;
  const jdText = document.getElementById("jd-text").value;
  if (!dir || !templateId || !jdText.trim()) {
    return setStatus("WORKSPACE, TEMPLATE, AND JD TEXT REQUIRED", "warning");
  }
  setStatus("SCANNING", "warning");
  const response = await api.sync_ast(dir, jdText, templateId);
  if (!response.ok) {
    setStatus("SCAN FAILED", "critical");
    document.getElementById("category-list").innerHTML = `<li>${response.error}</li>`;
    return;
  }
  lastScan = { jdText, templateId };
  const result = response.data;
  setGauge(result.g_force_score, result.alert_level);
  setStatus("SCAN COMPLETE", result.alert_level);

  document.getElementById("category-list").innerHTML = result.categories
    .map((c) => `<li>${c.name}: ${(c.coverage * 100).toFixed(0)}% (weight ${c.weight.toFixed(2)})</li>`)
    .join("");
  document.getElementById("gaps-list").innerHTML = result.gaps.map((g) => `<li>${g}</li>`).join("") || "<li>None</li>";
  document.getElementById("red-flags-list").innerHTML =
    result.red_flags.map((r) => `<li>${r}</li>`).join("") || "<li>None</li>";
});

// --- Templates -------------------------------------------------------------

document.getElementById("btn-validate-template").addEventListener("click", async () => {
  const api = requireApi();
  const path = document.getElementById("template-path").value.trim();
  const fix = document.getElementById("template-fix").checked;
  if (!path) return setStatus("ENTER A TEMPLATE PATH", "warning");
  const response = await api.validate_template(path, fix);
  renderJson("template-output", response);
  setStatus(response.ok && response.data.valid ? "TEMPLATE VALID" : "TEMPLATE INVALID",
    response.ok && response.data.valid ? "success" : "warning");
});

// --- Export ------------------------------------------------------------

document.getElementById("btn-export").addEventListener("click", async () => {
  const api = requireApi();
  const dir = currentWorkspaceDir();
  const name = document.getElementById("export-name").value.trim();
  const fmt = document.getElementById("export-format").value;
  if (!dir || !name) return setStatus("WORKSPACE AND BUNDLE NAME REQUIRED", "warning");
  const response = await api.export_bundle(dir, name, fmt, lastScan.jdText, lastScan.templateId);
  renderJson("export-output", response);
  setStatus(response.ok ? "BUNDLE EXPORTED" : "EXPORT FAILED", response.ok ? "success" : "critical");
});

// --- Vault ---------------------------------------------------------------

document.getElementById("btn-set-key").addEventListener("click", async () => {
  const api = requireApi();
  const dir = currentWorkspaceDir();
  const passphrase = document.getElementById("vault-passphrase").value;
  const apiKey = document.getElementById("vault-api-key").value;
  if (!dir || !passphrase || !apiKey) return setStatus("DIR, PASSPHRASE, AND KEY REQUIRED", "warning");
  const response = await api.set_llm_key(dir, passphrase, apiKey);
  renderJson("vault-output", response);
  setStatus(response.ok ? "KEY STORED" : "VAULT ERROR", response.ok ? "success" : "critical");
});

document.getElementById("btn-generate-narrative").addEventListener("click", async () => {
  const api = requireApi();
  const dir = currentWorkspaceDir();
  const passphrase = document.getElementById("vault-passphrase").value;
  if (!dir || !passphrase || !lastScan.jdText) {
    return setStatus("RUN A SCAN AND ENTER PASSPHRASE FIRST", "warning");
  }
  setStatus("CONTACTING LLM (NETWORK CALL)", "warning");
  const response = await api.generate_narrative(dir, lastScan.jdText, passphrase);
  renderJson("vault-output", response);
  setStatus(response.ok ? "NARRATIVE GENERATED" : "NARRATIVE FAILED", response.ok ? "success" : "critical");
});

// --- Bridge readiness ------------------------------------------------------

window.addEventListener("pywebviewready", () => {
  apiReady = true;
  setStatus("FLIGHT DECK ONLINE");
});

// Fallback for environments where the event fires before this script binds.
if (window.pywebview && window.pywebview.api) {
  apiReady = true;
  setStatus("FLIGHT DECK ONLINE");
}
