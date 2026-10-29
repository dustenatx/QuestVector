"""Assemble the browser/Pyodide spike into a folder that can be served locally.

Spike tooling only (see docs/spikes/2026-10-browser-pyodide.md); not part
of the questvector package. Downloads the pinned Pyodide runtime and the
wheels the core needs, checks every file against a known hash, and copies
in the prototype pages, a questvector wheel, and the synthetic test
fixtures. Downloads are cached in ``<out>/../vendor-cache`` so re-staging
is offline.

Usage:
    uv build --wheel --out-dir DIST
    uv run python spikes/browser-pyodide/stage.py --wheel DIST/questvector-*.whl --out SERVE_DIR
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

PYODIDE_VERSION = "314.0.7"  # released 14 Sep 2026, Python 3.14.2
PYODIDE_NPM_TARBALL = f"https://registry.npmjs.org/pyodide/-/pyodide-{PYODIDE_VERSION}.tgz"
PYODIDE_NPM_SHA512 = (
    "0YvXxEhfEdpLfb/XkM2BFAeMROq0iMUX2bzzH9pOttyMcWkwq+HbE5uyuGD82LN7y2q+SNvi/6V5JEsOlD2R1A=="
)
PYODIDE_PACKAGES_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
# Runtime files the page loads; the rest of the npm package (types,
# consoles, source maps) isn't needed.
PYODIDE_CORE_FILES = (
    "pyodide.mjs",
    "pyodide.asm.mjs",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
)
# Pyodide-built packages the core needs; their dependencies are added from
# pyodide-lock.json.
PYODIDE_PACKAGES = (
    "micropip",
    "cryptography",
    "lxml",
    "pyyaml",
    "pillow",
    "charset-normalizer",
    "typing-extensions",
)
# The exact files those packages and their dependencies resolve to in
# pyodide-lock.json. Pinned so the download allowlist below is complete;
# staging stops if the lock ever asks for anything else.
PYODIDE_PACKAGE_FILES = (
    "cffi-2.0.0-cp314-cp314-pyemscripten_2026_0_wasm32.whl",
    "charset_normalizer-3.4.7-py3-none-any.whl",
    "cryptography-47.0.0-cp314-abi3-pyemscripten_2026_0_wasm32.whl",
    "lxml-6.1.3-cp314-cp314-pyemscripten_2026_0_wasm32.whl",
    "micropip-0.11.1-py3-none-any.whl",
    "pillow-12.2.0-cp314-cp314-pyemscripten_2026_0_wasm32.whl",
    "pycparser-3.0-py3-none-any.whl",
    "pyyaml-6.0.3-cp314-cp314-pyemscripten_2026_0_wasm32.whl",
    "six-1.17.0-py2.py3-none-any.whl",
    "typing_extensions-4.15.0-py3-none-any.whl",
)
# Pure-Python wheels from PyPI that Pyodide doesn't build, with their PyPI
# sha256 digests.
PYPI_WHEELS = {
    "reportlab-5.0.1-py3-none-any.whl": (
        "https://files.pythonhosted.org/packages/db/cb/dacbc268cb68d0428ea2cbd85266195a9ab3e677449589ddae59bd7542ac/reportlab-5.0.1-py3-none-any.whl",
        "1c36e6bb0e71780c72331eba60da7f602e8d4389a8723825af71342e49d791e8",
    ),
    "python_docx-1.2.0-py3-none-any.whl": (
        "https://files.pythonhosted.org/packages/d0/00/1e03a4989fa5795da308cd774f05b704ace555a70f9bf9d3be057b680bcf/python_docx-1.2.0-py3-none-any.whl",
        "3fd478f3250fbbbfd3b94fe1e985955737c145627498896a8a6bf81f4baf66c7",
    ),
}
# Every URL this script may download, exactly. _fetch refuses anything else.
ALLOWED_URLS = frozenset(
    {
        PYODIDE_NPM_TARBALL,
        *(PYODIDE_PACKAGES_URL + name for name in PYODIDE_PACKAGE_FILES),
        *(url for url, _sha256 in PYPI_WHEELS.values()),
    }
)
PAGE_FILES = ("index.html", "core.html", "core.js", "steps.py", "files.html", "files.js", "spike.css")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIXTURES = {
    "Capabilities.md": REPO / "tests/fixtures/ollama_live/Capabilities.md",
    "Chronology.md": REPO / "tests/fixtures/ollama_live/Chronology.md",
    "Impact.md": REPO / "tests/fixtures/ollama_live/Impact.md",
    "job_description.txt": REPO / "tests/fixtures/ollama_live/job_description.txt",
    "v1-vault.json": REPO / "tests/fixtures/vault/v1-vault.json",
}


def _fetch(url: str, cache: Path) -> bytes:
    """Return the bytes at ``url``, from ``cache`` when already downloaded.

    Args:
        url: The file to download.
        cache: The cache file for this URL.

    Returns:
        The file's bytes.

    Raises:
        SystemExit: If ``url`` isn't HTTPS or isn't exactly one of
            ``ALLOWED_URLS``.
    """
    # Checked before the cache too, so a cached file is only ever used for
    # an allowed URL.
    if not url.startswith("https://"):
        raise SystemExit(f"refusing a non-HTTPS download: {url}")
    if url not in ALLOWED_URLS:
        raise SystemExit(f"refusing a download that isn't in the pinned allowlist: {url}")
    if cache.exists():
        return cache.read_bytes()
    # url is an exact match in the pinned ALLOWED_URLS above, and the caller
    # hash-verifies every download before using it.
    with urllib.request.urlopen(url, timeout=120) as response:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        data: bytes = response.read()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(data)
    return data


def _check(data: bytes, algorithm: str, expected: str, *, b64: bool = False) -> None:
    """Fail unless ``data`` hashes to ``expected``.

    Args:
        data: The downloaded bytes.
        algorithm: A hashlib algorithm name.
        expected: The expected digest, hex or base64.
        b64: Whether ``expected`` is base64 (npm integrity) rather than hex.

    Raises:
        SystemExit: On a mismatch.
    """
    digest = hashlib.new(algorithm, data).digest()
    actual = base64.b64encode(digest).decode() if b64 else digest.hex()
    if actual != expected:
        raise SystemExit(f"hash mismatch ({algorithm}): expected {expected}, got {actual}")


def _package_closure(lock: dict[str, object]) -> list[str]:
    """Return the Pyodide packages to stage, with their dependencies.

    Args:
        lock: The parsed pyodide-lock.json.

    Returns:
        Package names, sorted.
    """
    packages = lock["packages"]
    assert isinstance(packages, dict)
    seen: set[str] = set()
    pending = list(PYODIDE_PACKAGES)
    while pending:
        name = pending.pop()
        if name not in seen:
            seen.add(name)
            pending.extend(packages[name]["depends"])
    return sorted(seen)


def main() -> None:
    """Stage the spike into ``--out``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True, help="the questvector wheel from uv build")
    parser.add_argument("--out", type=Path, required=True, help="folder to serve (replaced)")
    args = parser.parse_args()

    out: Path = args.out.resolve()
    cache = out.parent / "vendor-cache"
    if out.exists():
        shutil.rmtree(out)
    pyodide_dir = out / "pyodide"
    wheels_dir = out / "wheels"
    fixtures_dir = out / "fixtures"
    for directory in (pyodide_dir, wheels_dir, fixtures_dir):
        directory.mkdir(parents=True)

    tarball = _fetch(PYODIDE_NPM_TARBALL, cache / f"pyodide-{PYODIDE_VERSION}.tgz")
    _check(tarball, "sha512", PYODIDE_NPM_SHA512, b64=True)
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as archive:
        for name in PYODIDE_CORE_FILES:
            member = archive.extractfile(f"package/{name}")
            assert member is not None
            (pyodide_dir / name).write_bytes(member.read())

    # The lock came from the verified tarball, so its hashes are trusted.
    lock = json.loads((pyodide_dir / "pyodide-lock.json").read_text(encoding="utf-8"))
    packages = _package_closure(lock)
    for name in packages:
        entry = lock["packages"][name]
        data = _fetch(PYODIDE_PACKAGES_URL + entry["file_name"], cache / entry["file_name"])
        _check(data, "sha256", entry["sha256"])
        (pyodide_dir / entry["file_name"]).write_bytes(data)

    for filename, (url, sha256) in PYPI_WHEELS.items():
        data = _fetch(url, cache / filename)
        _check(data, "sha256", sha256)
        (wheels_dir / filename).write_bytes(data)
    shutil.copy2(args.wheel, wheels_dir / args.wheel.name)

    for name, source in FIXTURES.items():
        shutil.copy2(source, fixtures_dir / name)
    for name in PAGE_FILES:
        shutil.copy2(HERE / name, out / name)

    manifest = {
        "pyodide_version": PYODIDE_VERSION,
        "pyodide_packages": packages,
        "wheels": sorted(path.name for path in wheels_dir.iterdir()),
        "fixtures": sorted(FIXTURES),
        "bytes": {
            str(path.relative_to(out)): path.stat().st_size
            for path in sorted(out.rglob("*"))
            if path.is_file()
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total = sum(manifest["bytes"].values())  # type: ignore[attr-defined]
    print(f"Staged {len(manifest['bytes'])} files, {total / 1e6:.1f} MB, into {out}")


if __name__ == "__main__":
    main()
