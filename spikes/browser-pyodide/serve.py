"""Serve the staged spike on 127.0.0.1 with a chosen Content Security Policy.

Spike tooling only. ``python -m http.server`` can't add response headers,
so this wraps it to send a CSP header and to disable caching only when
asked (the cached-reload measurement needs normal caching).

Usage:
    uv run python spikes/browser-pyodide/serve.py SERVE_DIR [--csp strict|eval|cdn|probe|none] [--port 8765]
"""

from __future__ import annotations

import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

AI_HOSTS = "https://api.anthropic.com https://api.openai.com https://generativelanguage.googleapis.com"
JSDELIVR = "https://cdn.jsdelivr.net"
PYPI = "https://pypi.org https://files.pythonhosted.org"

# The starting point for the CSP search (spike step 7). Each directive
# beyond these is added only when the browser reports a violation; the
# write-up records which ones were needed and why.
STRICT = {
    "default-src": "'none'",
    "script-src": "'self' 'wasm-unsafe-eval'",
    "connect-src": f"'self' {AI_HOSTS}",
    "style-src": "'self'",
    "img-src": "'self' blob: data:",
    "base-uri": "'none'",
    "form-action": "'none'",
    "frame-ancestors": "'none'",
}


def _policy(mode: str) -> str | None:
    """Build the CSP header value for a mode.

    Args:
        mode: ``strict`` (self-hosted), ``cdn`` (Pyodide from jsDelivr),
            ``probe`` (strict plus PyPI, for the dependency-resolution
            probe), ``eval`` (strict plus ``'unsafe-eval'``, to compare
            against strict if Emscripten's eval of EM_JS code is blocked),
            or ``none``.

    Returns:
        The header value, or ``None`` for no CSP.
    """
    if mode == "none":
        return None
    directives = dict(STRICT)
    if mode == "eval":
        directives["script-src"] += " 'unsafe-eval'"
    if mode == "cdn":
        directives["script-src"] += f" {JSDELIVR}"
        directives["connect-src"] += f" {JSDELIVR}"
    if mode == "probe":
        directives["connect-src"] += f" {PYPI}"
    return "; ".join(f"{name} {value}" for name, value in directives.items())


class _Handler(SimpleHTTPRequestHandler):
    """Static file handler that adds the CSP header."""

    csp: str | None = None
    no_cache = False

    def end_headers(self) -> None:
        if self.csp:
            self.send_header("Content-Security-Policy", self.csp)
        if self.no_cache:
            self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    """Run the server until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--csp", choices=("strict", "eval", "cdn", "probe", "none"), default="strict")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-cache", action="store_true", help="send Cache-Control: no-store")
    args = parser.parse_args()

    _Handler.csp = _policy(args.csp)
    _Handler.no_cache = args.no_cache
    handler = functools.partial(_Handler, directory=str(args.root.resolve()))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Serving {args.root} at http://127.0.0.1:{args.port}/  (CSP: {args.csp})")
    if _Handler.csp:
        print(f"Content-Security-Policy: {_Handler.csp}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
