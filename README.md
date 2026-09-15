# 🚀 QuestVector
### *This is a proof of concept project which has never been tested. Use at your own risk*
### *Command your job search with a local-only, privacy-first career flight deck. Deconstruct JDs, track applications, and own your career data.*

[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING_TEMPLATES.md)

QuestVector is an open-source, local-first career management platform built for experienced IT professionals (5–10+ years).

## What actually exists right now

This repo describes **two** implementations of the QuestVector concept, but only one of them has been built:

| | Python Desktop (this build) | Web Cockpit |
|---|---|---|
| **Status** | ✅ Implemented, tested, runs today | 🚧 Design target only — no code exists yet |
| Stack | Pure Python core + `qv` CLI + pywebview shell | React/Tailwind UI + Rust-compiled Wasm core (planned) |
| Distribution | Clone/`pip install` and run locally | Will clone & run locally when built (see [Roadmap](#-roadmap-web-cockpit-not-yet-built) below) |
| Storage | Local filesystem + AES-256-GCM encrypted vault file | File System Access API + IndexedDB (planned) |

**If you just want to use QuestVector today, skip straight to [Quickstart](#-quickstart) below — it's all Python.** The Web Cockpit section further down is a roadmap, not a tutorial.

**Distribution policy for this project: nothing is published externally.** No public domain, no hosted service, no npm-registry package, for either implementation, ever. Everything is cloned and run entirely from local files — a deliberate decision, not a temporary gap.

The two implementations share the same *concept* — a local career dossier scored against job descriptions via weighted mission templates — but are separate codebases in separate languages. The G-Force matching formula in the Python build is independently defined (documented in `questvector/core/matcher.py`) since the original spec never publishes a scoring algorithm; if the Web Cockpit is ever built, the two engines are not guaranteed to produce identical scores for identical inputs.

---

## 🚀 Quickstart

This is the only implementation that exists — there is nothing else to install or run.

```bash
git clone https://github.com/dustenatx/QuestVector.git
cd QuestVector

python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,llm]"        # omit [llm] to skip all optional LLM SDKs
```

`[llm]` installs the SDKs for all three cloud narrative-generation providers (Anthropic, OpenAI, Gemini) at once; install `[llm-anthropic]`, `[llm-openai]`, or `[llm-gemini]` individually if you only want one. The fourth supported provider, a local Ollama server, needs no extra install here at all — see "Optional LLM narrative generation" below.

`pip install` needs one-time internet access to fetch dependencies from PyPI, the same as any Python/Node/Rust project needs its package registry at install time — after that, everything below runs fully offline (with the single explicit exception noted under "Optional LLM narrative generation").

```bash
qv launch --dir ~/career-workspace
qv sync-ast --dir ~/career-workspace --target jd.txt --template devops-senior-mgr
qv template validate ~/career-workspace/templates/starter/devops-senior-mgr.qv-mission.yaml --fix
qv export --dir ~/career-workspace --bundle acme-resume --format pdf \
    --target jd.txt --template devops-senior-mgr
qv vault set-key --provider anthropic --dir ~/career-workspace   # store a provider + key, only if you want narrative generation

python -m questvector.desktop.app   # native HUD window (requires a display)
```

### Tests
```bash
pytest                                          # 142 tests
pytest --cov=questvector --cov-report=term-missing
```

### Version
```bash
qv --version                                    # reads questvector.__version__ (pyproject.toml sources from it too)
```

---

## 🧭 Features (Python build — this is what exists)

* **`qv` CLI** (stdlib `argparse`) — `launch`, `sync-ast`, `export`, `template validate`, `vault set-key`.
* **AST Block Matching:** Deconstruct target Job Descriptions and map them against your career chronology and capabilities.
* **Community Mission Templates:** Pre-built matching profiles for Senior DevOps, Cybersecurity, Platform Engineering, IT Project Management, and more (7 starter templates included).
* **Native desktop app** (pywebview) themed to the Tactical Ops Flight Deck HUD, including a live G-Force gauge.
* **PDF/DOCX export** of the dossier and match summary (reportlab / python-docx).
* **Encrypted local vault** (AES-256-GCM) for provider settings and API keys.
* **Local-first storage:** Your dossier and career data live on disk, not in a vendor's database.
* **Optional LLM narrative generation, four provider choices** — an explicit, user-triggered action (`qv export --narrative`, or the desktop UI's "Generate Narrative" button) that drafts a tailored resume summary. Pick one provider via `qv vault set-key --provider <name>`:

  | Provider | Runs | Needs an API key? | Get a key |
  |---|---|---|---|
  | `anthropic` (Claude) | Remote | Yes | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
  | `openai` | Remote | Yes | [platform.openai.com](https://platform.openai.com/api-keys) — **note:** this is the OpenAI Platform, the API behind ChatGPT, not a ChatGPT Plus login; they're separate accounts and separate billing. |
  | `gemini` (Google) | Remote | Yes | [aistudio.google.com](https://aistudio.google.com/apikey) |
  | `ollama` | **Local** | No | [ollama.com](https://ollama.com/download) — install it, run it, `ollama pull <model>` |

  The three remote providers are the *only* code paths in this build that make an outbound network call, and each is off unless you configure it and explicitly ask for narrative generation; connecting a remote provider requires your own account/subscription with that provider (with data-sharing/training disabled if you want to preserve zero-tracking) and is subject to that provider's usage fees. `ollama` is the exception: once it's installed and running, narrative generation through it never leaves your machine. The CLI and desktop UI print each provider's setup link and this same OpenAI/ChatGPT clarification at the moment you configure it, so you're not left guessing where to go.

  **Extensible by design:** the four providers above live in one data-driven registry (`questvector/core/llm.py`'s `PROVIDERS`), each entry pairing its metadata with a small factory function. The CLI's `--provider` choices and the desktop UI's provider dropdown both read that registry directly, so a fifth provider (remote or local) is three additions to that one file — a generator class, a factory function, and a registry entry — with no changes needed anywhere else. See that module's docstring for the exact steps.

---

## 🗺️ Roadmap: Web Cockpit (not yet built)

**Short answer: yes, it will run locally — the same as the Python build, just not written yet.** Nothing below this line exists as code today; this section documents the *design target* from `MASTER_DEVELOPER_SPEC.pdf` and the constraint it must be built under. Do not trust any `questvector.dev` URL, `npx questvector`, or `npm install questvector` command as real; none of them exist, and none ever will — see the distribution policy above.

**Planned stack:** React/Tailwind UI + a Rust-compiled Wasm core, using the browser's File System Access API and IndexedDB for local storage — no server component.

**How it will run, once built** (no public domain, no npm package, ever):
1. Clone this repo.
2. Install dependencies and build the Wasm/React bundle locally (exact commands land here once the code exists).
3. Serve the built output from `localhost` (e.g. a one-line local static-file server) and open it in a browser — `localhost` (unlike a plain `file://` page) qualifies as a secure context for the File System Access API.

That's the whole distribution model: clone → build → serve from `localhost`. No hosted URL, no CDN, no registry install, then or ever. A Node-based CLI (a `qv`-equivalent wrapping the same Wasm core) would follow the same rule — run only from a local clone, never via `npx <package>` from the public registry.

Exact build/run commands will be added here once this implementation actually exists.

---

## 🤝 Contributing
Interested in building or submitting custom `.qv-mission.yaml` templates? Check out our [Community Template Contribution Guide](CONTRIBUTING_TEMPLATES.md). Templates go in `templates/community/`; built-in ones ship in `templates/starter/`. The schema in that guide and the one `questvector/core/templates.py` validates against have been reconciled into one — see that module's docstring for the full merge notes.

License: [MIT](LICENSE)
