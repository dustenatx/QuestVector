# 0005. Ollama called over plain HTTP, no SDK

- **Status:** Accepted
- **Date:** 2026-09-15

## Context
Ollama runs as a local server the user installs. A Python client library
exists, but would be one more dependency for a few HTTP calls.

## Decision
Call Ollama's HTTP API with the standard library (`urllib.request`), with a
configurable host (`--host`). Ollama needs no install extra and no API key.

## Consequences
- The fully local, zero-cost path has no extra dependencies.
- Narrative generation through Ollama never leaves the machine.
- The request and response handling is maintained in this codebase rather
  than by a library, so changes to Ollama's API need a manual update.
