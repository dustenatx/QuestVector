# 0002. AES-256-GCM encrypted local vault file

- **Status:** Accepted
- **Date:** 2026-09-09 (per-provider fields added 2026-09-15)

## Context
LLM provider API keys and settings must persist between runs. The original
spec named browser IndexedDB, which doesn't apply to a Python desktop build.
Plain-text config files would expose keys to anything that can read the disk.

## Decision
Store provider settings and keys in one local JSON file encrypted with
AES-256-GCM (`cryptography`'s `AESGCM`). The key is derived from a user
passphrase with PBKDF2-HMAC-SHA256 (390,000 iterations) and a random salt.
On POSIX systems the file is set to owner read/write only. On 15 Sep the
single key field became per-provider fields, with automatic migration of
older vault files.

## Consequences
- Keys are protected at rest without depending on an OS keychain.
- A forgotten passphrase means the vault must be recreated; keys are not
  recoverable.
- **Revisit:** OWASP's current guidance for PBKDF2-HMAC-SHA256 is 600,000
  iterations. Raising it needs a migration path for existing vaults, and
  scrypt or Argon2 are alternatives. Tracked under backlog item 1.
