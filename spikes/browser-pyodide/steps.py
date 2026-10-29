"""The spike's Python steps, run inside Pyodide by core.js (browser) and smoke.mjs (Node).

Spike code only. Each step calls the unmodified questvector core on the
synthetic fixtures (written to ``FIXTURES`` by the caller) and returns a
JSON-able dict; the caller does the timing. Nothing here touches real
career data or the network.
"""

from __future__ import annotations

import json
import platform
import sys
import time
import traceback
from pathlib import Path
from typing import Any

FIXTURES = Path("/home/pyodide/fixtures")
WORKSPACE = Path("/home/pyodide/ws")
TEMPLATE_ID = "devops-senior-mgr"
SPIKE_PASSPHRASE = "qv-spike-passphrase"  # synthetic, for the round trip only
V1_PASSPHRASE = "qv-fixture-v1-passphrase"  # documented in tests/fixtures/vault/README.md
KDF_SALT = b"qv-spike-salt-16"  # fixed, so WebCrypto and Pyodide derive the same key
KDF_ITERATIONS = 1_000_000

_state: dict[str, Any] = {}


def _try(probe: Any) -> str:
    """Run a probe and describe the outcome.

    Args:
        probe: A zero-argument callable.

    Returns:
        ``"ok: ..."`` or ``"fails: ExceptionType: message"``.
    """
    try:
        return f"ok: {probe()}"
    except BaseException as exc:  # noqa: BLE001 -- a probe reports, never raises
        return f"fails: {type(exc).__name__}: {exc}"


def probe_platform() -> dict[str, Any]:
    """Report the interpreter and which OS features work on Emscripten."""
    import os
    import tempfile

    def thread() -> str:
        import threading

        thread = threading.Thread(target=lambda: None)
        thread.start()
        thread.join()
        return "thread started"

    def subprocess_run() -> str:
        import subprocess

        return str(subprocess.run(["true"], check=False).returncode)

    def fs_ops() -> str:
        directory = Path(tempfile.mkdtemp())
        fd, name = tempfile.mkstemp(dir=directory)
        os.fchmod(fd, 0o600)
        os.write(fd, b"x")
        os.fsync(fd)
        os.close(fd)
        os.replace(name, directory / "final")
        dir_fd = os.open(directory, os.O_RDONLY)
        os.fsync(dir_fd)
        os.close(dir_fd)
        return f"mkstemp/fchmod/fsync/replace/dir-fsync, mode {oct((directory / 'final').stat().st_mode & 0o777)}"

    return {
        "python": sys.version,
        "platform": sys.platform,
        "machine": platform.machine(),
        "home": str(Path.home()),
        "pid": os.getpid(),
        "threading": _try(thread),
        "subprocess": _try(subprocess_run),
        "filesystem": _try(fs_ops),
    }


async def install(wheel_urls: list[str]) -> dict[str, Any]:
    """Install the local wheels with micropip, never reaching PyPI.

    The questvector wheel goes in with ``deps=False``: its pywebview
    dependency needs proxy-tools, which exists only as an sdist (see the
    probe). reportlab and python-docx resolve their dependencies against the
    Pyodide packages already loaded, so a missing one would show up as a
    failed lookup rather than a silent download.

    Args:
        wheel_urls: URLs (or ``emfs:`` paths) of the local wheels.

    Returns:
        The installed version of each core dependency.
    """
    import micropip  # type: ignore[import-not-found]

    qv = [url for url in wheel_urls if "questvector-" in url]
    others = [url for url in wheel_urls if url not in qv]
    await micropip.install(others, index_urls=[])
    await micropip.install(qv, deps=False, index_urls=[])
    listing = micropip.list()
    names = ("questvector", "pyyaml", "cryptography", "cffi", "python-docx", "lxml", "reportlab",
             "pillow", "charset-normalizer", "typing-extensions", "pywebview")
    return {name: (listing[name].version, listing[name].source) if name in listing else None for name in names}


async def probe_full_install(wheel_url: str) -> dict[str, Any]:
    """Try the normal install (dependencies resolved from PyPI) and report the outcome.

    Args:
        wheel_url: URL of the questvector wheel.

    Returns:
        ``{"result": ...}`` with the success or the error text.
    """
    import micropip

    try:
        await micropip.install(wheel_url)
    except BaseException as exc:  # noqa: BLE001 -- the probe reports the failure
        return {"result": f"fails: {type(exc).__name__}: {exc}"}
    return {"result": "ok", "installed": sorted(micropip.list())}


def step_parse() -> dict[str, Any]:
    """Create a workspace, copy the synthetic dossier in, and parse it."""
    from questvector.core import markdown_parser, workspace

    WORKSPACE.mkdir(parents=True, exist_ok=True)
    for name in ("Capabilities.md", "Chronology.md", "Impact.md"):
        (WORKSPACE / name).write_text((FIXTURES / name).read_text(encoding="utf-8"), encoding="utf-8")
    init = workspace.init_workspace(WORKSPACE)  # seeds templates/starter from package data
    with workspace.WorkspaceLock(WORKSPACE):  # O_EXCL lock file on MEMFS
        dossier = markdown_parser.parse_dossier(WORKSPACE)
    _state["dossier"] = dossier
    return {
        "capabilities": len(dossier.capabilities),
        "chronology": len(dossier.chronology),
        "impact": len(dossier.impact),
        "starter_templates_copied": len(list((WORKSPACE / "templates" / "starter").glob("*.yaml"))),
        "init_created_files": len(init.created_files),
    }


def step_match() -> dict[str, Any]:
    """Match the dossier against a starter template and the synthetic job description."""
    from questvector.core import matcher, templates

    path = templates.find_template_file([WORKSPACE / "templates" / "starter"], TEMPLATE_ID)
    if path is None:
        raise RuntimeError(f"starter template {TEMPLATE_ID} not found")
    template = templates.load_template(path)
    jd_text = (FIXTURES / "job_description.txt").read_text(encoding="utf-8")
    job = matcher.parse_job_description(jd_text, source="job_description.txt")
    result = matcher.run_match(_state["dossier"], job, template)
    _state["match"] = result
    return {"template": TEMPLATE_ID, "g_force": round(result.g_force_score, 2), "alert_level": str(result.alert_level), "gaps": len(result.gaps)}


def step_export(fmt: str) -> dict[str, Any]:
    """Export the dossier with the match summary as DOCX or PDF.

    Args:
        fmt: ``"docx"`` or ``"pdf"``.

    Returns:
        The output path (read back by the caller for the download) and size.
    """
    from questvector.core.exporter import export_bundle

    out = WORKSPACE / "bundles" / f"spike-dossier.{fmt}"
    export_bundle(_state["dossier"], out, fmt=fmt, match_result=_state["match"])  # type: ignore[arg-type]
    return {"path": str(out), "bytes": out.stat().st_size}


def step_vault() -> dict[str, Any]:
    """Save and load a vault at the shipped 1M iterations, then open the format 1 fixture."""
    from questvector.core import vault

    path = WORKSPACE / ".questvector.vault"
    data = vault.VaultData(
        llm_provider="anthropic",
        llm_api_keys={"anthropic": "QVSPIKE-not-a-real-key"},
        session_cache={"spike": 1},
    )
    start = time.perf_counter()
    vault.save_vault(path, SPIKE_PASSPHRASE, data)
    saved = time.perf_counter()
    loaded = vault.load_vault(path, SPIKE_PASSPHRASE)
    done = time.perf_counter()
    v1 = vault.load_vault(FIXTURES / "v1-vault.json", V1_PASSPHRASE)
    v1_done = time.perf_counter()
    stored = json.loads(path.read_text(encoding="utf-8"))
    return {
        "iterations": vault._KDF_ITERATIONS,
        "save_ms": round((saved - start) * 1000),
        "load_ms": round((done - saved) * 1000),
        "round_trip_equal": loaded == data,
        "file_mode": oct(path.stat().st_mode & 0o777),
        "format": stored["version"],
        "v1_load_ms": round((v1_done - done) * 1000),
        "v1_contents_ok": v1.llm_provider == "anthropic"
        and v1.api_key_for("anthropic") == "QVFIXTURE-v1-not-a-real-key"
        and v1.session_cache == {"a": 1},
    }


def step_kdf() -> dict[str, Any]:
    """Derive a key with Pyodide's cryptography build, for comparison with WebCrypto."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    start = time.perf_counter()
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=KDF_SALT, iterations=KDF_ITERATIONS).derive(
        SPIKE_PASSPHRASE.encode("utf-8")
    )
    return {"ms": round((time.perf_counter() - start) * 1000), "key_hex": key.hex()}


def run(name: str, *args: Any) -> str:
    """Run a step by name and return its result as JSON, catching any failure.

    Args:
        name: A function in this module.
        *args: Its arguments.

    Returns:
        JSON: ``{"ok": true, "data": ...}`` or ``{"ok": false, "error": ..., "traceback": ...}``.
    """
    try:
        return json.dumps({"ok": True, "data": globals()[name](*args)})
    except BaseException as exc:  # noqa: BLE001 -- reported to the page
        return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})


async def run_async(name: str, *args: Any) -> str:
    """Async counterpart of :func:`run`, for the micropip steps."""
    try:
        return json.dumps({"ok": True, "data": await globals()[name](*args)})
    except BaseException as exc:  # noqa: BLE001 -- reported to the page
        return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})
