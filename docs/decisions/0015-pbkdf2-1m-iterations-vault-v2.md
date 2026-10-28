# 0015. Vault key derivation: PBKDF2 at 1,000,000 iterations, settings stored in the file

- **Status:** Accepted
- **Date:** 2026-10-28

## Context
[ADR-0002](0002-aes-256-gcm-local-vault.md) derives the vault key with
PBKDF2-HMAC-SHA256 at 390,000 iterations. OWASP's Password Storage Cheat
Sheet (checked 28 Oct 2026) sets 600,000 as the minimum for
PBKDF2-HMAC-SHA256. The vault file (format 1) didn't record the KDF or its
iteration count, so changing either would have made every existing vault
unreadable.

Time for one key derivation on the owner's Mac (Apple M3, 24 GB, Python
3.14.8, cryptography 50.0.2; median of 7 runs, 28 Oct 2026):

| Iterations | Median | Min–max |
|---|---|---|
| 390,000 (format 1) | 58.7 ms | 58.5–61.8 |
| 600,000 (OWASP minimum) | 90.0 ms | 89.9–90.2 |
| 1,000,000 | 150.0 ms | 149.7–151.4 |
| 2,000,000 | 301.1 ms | 299.7–303.6 |
| 10,000,000 (2 runs) | 1,504 ms | 1,502–1,507 |

Options considered:
- **Argon2id.** OWASP's first choice, and memory-hard, which makes GPU and
  ASIC guessing much more expensive. It is in the `cryptography` package
  QuestVector already depends on (since version 44), so it needed no new
  dependency. Not chosen, by the owner's decision of 28 Oct 2026.
- **PBKDF2-HMAC-SHA256 at 600,000.** Meets the minimum with no margin for
  the next revision of the guidance.
- **PBKDF2-HMAC-SHA256 at 1,000,000.** Chosen.

## Decision
- New vaults derive their key with PBKDF2-HMAC-SHA256 at 1,000,000
  iterations: about 150 ms per unlock on the machine above, and about 0.3 s
  for `qv vault set-key`, which reads and then re-saves.
- **Format 2** records the KDF in the file and authenticates it:

  ```json
  {"version": 2,
   "kdf": {"name": "pbkdf2-hmac-sha256", "iterations": 1000000, "salt": "<base64, 16 bytes>"},
   "nonce": "<base64, 12 bytes>",
   "ciphertext": "<base64: AES-256-GCM ciphertext followed by its 16-byte tag>"}
  ```

  The version, KDF name, iteration count, and salt are passed to AES-GCM as
  associated data: compact JSON with sorted keys, rebuilt from the parsed
  values. Changing any of them makes decryption fail.
- On read, the iteration count must be between 600,000 and 5,000,000,
  checked before any key is derived. The cap (about 0.75 s here) stops a
  crafted file from stalling unlock, and leaves room to raise the default
  without a format change.
- Format 1 files still open, at their fixed 390,000 iterations. Every save
  writes format 2, so a format 1 vault is upgraded the next time it is
  saved, with the passphrase that save already asks for. Reading a vault
  never rewrites it. Format 1 is never written. Any other version fails with
  a `VaultError` naming the version.
- Saves are atomic: a temporary file in the same folder, created
  owner-read/write only, flushed to disk, then renamed over the vault. A
  crash leaves the old vault or the new one, never a partial file.
- A new vault needs a non-empty passphrase, and `qv vault set-key` asks for
  it twice. An existing vault with an empty passphrase still opens and
  saves.

## Consequences
- Unlock is about 90 ms slower than before.
- PBKDF2 isn't memory-hard, so an attacker with GPUs or ASICs gains more
  than they would against Argon2id; passphrase length matters more than the
  iteration count. The `kdf.name` field lets a later format add Argon2id
  without breaking format 2 vaults. Revisit if the owner's decision changes.
- QuestVector 1.1.0 and earlier can't open a format 2 vault ("Unsupported
  vault format version: 2"). Going back to 1.1.0 means recreating the vault.
- The minimum and the cap are constants in `questvector/core/vault.py`, so
  changing them is a code change and a release.
- **Windows:** the rename is still atomic within one drive, but fails (and
  leaves the old vault intact) if another program has the file open.
  `chmod` only toggles the read-only flag there, so who can read the file
  depends on the folder's permissions; inside the user's profile that is
  normally that user and administrators.
- The test suite runs vault tests at 1,000 iterations through a fixture in
  `tests/conftest.py`; tests marked `real_kdf` check the shipped settings.
- The system spec (`docs/QuestVector_Spec.pdf`, §3.1) still shows 390,000
  iterations until it is regenerated (backlog item 3).
