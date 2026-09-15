"""QuestVector — local-first career navigation & flight deck platform.

This package is the Python desktop implementation described in the Stage 1
blueprint response to MASTER_DEVELOPER_SPEC.pdf: the original spec describes
a browser/React/Rust-Wasm application, which has no direct Python
equivalent, so this package reimplements the portable core logic (Markdown
AST parsing, the Micro-Diff Matching Engine, YAML mission-template
validation, PDF/DOCX export, an encrypted local vault, and an LLM narrative
integration) plus a ``qv`` CLI and a pywebview desktop shell themed to the
spec's "Tactical Ops Flight Deck" brand.
"""

from __future__ import annotations

__version__ = "1.0.0"
