"""Encrypted local vault for secrets and session cache.

Spec reference: MASTER_DEVELOPER_SPEC.pdf Section 2 specifies an "IndexedDB
(Local Vault)" using "Dexie.js / AES-GCM" to cache directory handles, store
"Encrypted LLM keys," and cache the template registry. IndexedDB is a
browser-only API with no Python equivalent, so this module reimplements the
same *guarantee* — AES-256-GCM authenticated encryption at rest, keyed by a
user passphrase — as a single local JSON file instead.

Per the Stage 1 blueprint decision to include real LLM integration (see
:mod:`questvector.core.llm`), this vault is where the user's LLM provider
selection and API key(s) are stored: never in plaintext, never logged, and
never in the Markdown dossier files themselves. Multiple cloud providers'
keys can be stored side by side (see :class:`VaultData`), so switching the
active provider doesn't require re-entering a key that was already saved.
"""

from __future__ import annotations

import base64
import json
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from questvector.exceptions import VaultError

_KDF_ITERATIONS = 390_000
_SALT_BYTES = 16
_NONCE_BYTES = 12
_KEY_BYTES = 32  # AES-256
_VAULT_FORMAT_VERSION = 1


@dataclass(slots=True)
class VaultData:
    """Plaintext contents of an unlocked vault.

    Attributes:
        llm_provider: Which configured provider (see
            :data:`questvector.core.llm.PROVIDERS`) is active for narrative
            generation -- e.g. ``"anthropic"``, ``"openai"``, ``"gemini"``,
            or ``"ollama"`` -- or ``None`` if nothing has been configured
            yet.
        llm_api_keys: API keys for cloud providers, keyed by provider id.
            The local ``"ollama"`` provider never has an entry here since
            it needs no key.
        llm_model: Optional model override for ``llm_provider``. ``None``
            means use that provider's default model.
        llm_host: Optional server override, used only by the local
            ``"ollama"`` provider to point at a non-default local server.
        session_cache: Arbitrary small key/value cache (e.g. the "template
            registry cache" from the spec) — not intended for large data.
    """

    llm_provider: str | None = None
    llm_api_keys: dict[str, str] = field(default_factory=dict)
    llm_model: str | None = None
    llm_host: str | None = None
    session_cache: dict[str, Any] = field(default_factory=dict)

    def api_key_for(self, provider: str) -> str | None:
        """Look up the stored API key for a provider, if any.

        Args:
            provider: Provider id (e.g. ``"anthropic"``).

        Returns:
            The stored key, or ``None`` if no key is stored for that
            provider (always ``None`` for ``"ollama"``, which needs none).
        """
        return self.llm_api_keys.get(provider)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-encodable dict.

        Returns:
            A plain dict with the LLM provider fields and ``session_cache``.
        """
        return {
            "llm_provider": self.llm_provider,
            "llm_api_keys": self.llm_api_keys,
            "llm_model": self.llm_model,
            "llm_host": self.llm_host,
            "session_cache": self.session_cache,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VaultData:
        """Reconstruct from a decoded dict.

        Transparently migrates the single-provider vault schema used before
        multi-provider support existed (a bare ``llm_api_key`` string,
        always Anthropic) into the current ``llm_provider``/``llm_api_keys``
        shape, so an older vault file keeps working without the user having
        to re-run ``qv vault set-key``.

        Args:
            data: The dict produced by :meth:`to_dict` (or an older
                version's equivalent).

        Returns:
            A :class:`VaultData` instance.
        """
        llm_api_keys = dict(data.get("llm_api_keys") or {})
        llm_provider = data.get("llm_provider")

        legacy_key = data.get("llm_api_key")
        if legacy_key and "llm_provider" not in data:
            llm_provider = "anthropic"
            llm_api_keys.setdefault("anthropic", legacy_key)

        return cls(
            llm_provider=llm_provider,
            llm_api_keys=llm_api_keys,
            llm_model=data.get("llm_model"),
            llm_host=data.get("llm_host"),
            session_cache=dict(data.get("session_cache", {})),
        )


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from a passphrase and salt via PBKDF2-HMAC-SHA256.

    Args:
        passphrase: The user-supplied vault passphrase.
        salt: A random per-vault salt.

    Returns:
        A 32-byte key suitable for AES-256-GCM.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=_KEY_BYTES, salt=salt, iterations=_KDF_ITERATIONS
    )
    return kdf.derive(passphrase.encode("utf-8"))


def _restrict_permissions(path: Path) -> None:
    """Best-effort restriction of a file to owner read/write only.

    Args:
        path: The file to restrict. No-op (never raises) on platforms
            where ``chmod`` semantics don't apply the same way (Windows).
    """
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def save_vault(path: Path, passphrase: str, data: VaultData) -> None:
    """Encrypt and write vault data to disk, overwriting any existing file.

    Args:
        path: Destination vault file path.
        passphrase: Passphrase used to derive the encryption key.
        data: The vault contents to encrypt.

    Raises:
        VaultError: If the file cannot be written.
    """
    salt = os.urandom(_SALT_BYTES)
    nonce = os.urandom(_NONCE_BYTES)
    key = _derive_key(passphrase, salt)
    plaintext = json.dumps(data.to_dict()).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, associated_data=None)

    envelope = {
        "version": _VAULT_FORMAT_VERSION,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }
    try:
        path.write_text(json.dumps(envelope), encoding="utf-8")
    except OSError as exc:
        raise VaultError(f"Could not write vault file: {path}", context={"path": str(path)}) from exc
    _restrict_permissions(path)


def load_vault(path: Path, passphrase: str) -> VaultData:
    """Read and decrypt a vault file.

    Args:
        path: Vault file path.
        passphrase: Passphrase to derive the decryption key.

    Returns:
        The decrypted :class:`VaultData`.

    Raises:
        VaultError: If the file is missing, not valid JSON/base64, was
            written by an incompatible/future version, or the passphrase is
            wrong (authentication tag mismatch).
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise VaultError(f"Vault file not found: {path}", context={"path": str(path)}) from exc
    except OSError as exc:
        raise VaultError(f"Could not read vault file: {path}", context={"path": str(path)}) from exc

    try:
        envelope = json.loads(raw)
        version = envelope["version"]
        salt = base64.b64decode(envelope["salt"])
        nonce = base64.b64decode(envelope["nonce"])
        ciphertext = base64.b64decode(envelope["ciphertext"])
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise VaultError(
            f"Vault file is corrupted or not a QuestVector vault: {path}",
            context={"path": str(path)},
        ) from exc

    if version != _VAULT_FORMAT_VERSION:
        raise VaultError(
            f"Unsupported vault format version: {version}",
            context={"path": str(path), "version": version},
        )

    key = _derive_key(passphrase, salt)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, associated_data=None)
    except InvalidTag as exc:
        raise VaultError(
            "Incorrect passphrase or corrupted vault data", context={"path": str(path)}
        ) from exc

    try:
        decoded = json.loads(plaintext.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise VaultError(
            f"Vault decrypted but content is corrupted: {path}", context={"path": str(path)}
        ) from exc

    return VaultData.from_dict(decoded)


def update_vault(
    path: Path, passphrase: str, mutate: Callable[[VaultData], None]
) -> VaultData:
    """Load a vault (or start empty if none exists), mutate it, and save it.

    Args:
        path: Vault file path.
        passphrase: Passphrase used for both decrypt and re-encrypt.
        mutate: A callable ``(VaultData) -> None`` that mutates the loaded
            data in place.

    Returns:
        The updated, now-persisted :class:`VaultData`.

    Raises:
        VaultError: Propagated from :func:`load_vault` (for a wrong
            passphrase against an existing vault) or :func:`save_vault`.
    """
    data = load_vault(path, passphrase) if path.exists() else VaultData()
    mutate(data)
    save_vault(path, passphrase, data)
    return data
