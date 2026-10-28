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

File format 2 (ADR-0015) records the key-derivation settings in the file and
authenticates them as AES-GCM associated data::

    {"version": 2,
     "kdf": {"name": "pbkdf2-hmac-sha256", "iterations": 1000000,
             "salt": "<base64, 16 bytes>"},
     "nonce": "<base64, 12 bytes>",
     "ciphertext": "<base64: ciphertext followed by the 16-byte GCM tag>"}

Format 1 files (390,000 iterations, settings not recorded) still open, and
are rewritten as format 2 the next time they are saved. Format 1 is never
written.
"""

from __future__ import annotations

import base64
import json
import os
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from questvector import __version__
from questvector.exceptions import VaultError

# Key derivation (ADR-0015). The functions below read these module globals
# when called, never as default argument values, so they can be patched
# (the test suite lowers the iteration count to stay fast).
_KDF_NAME = "pbkdf2-hmac-sha256"
_KDF_ITERATIONS = 1_000_000  # written by save_vault
_MIN_KDF_ITERATIONS = 600_000  # OWASP minimum; lower counts are rejected on read
_MAX_KDF_ITERATIONS = 5_000_000  # cap, so a crafted file can't stall unlock
_V1_KDF_ITERATIONS = 390_000  # the fixed setting of format 1 (read only)
_SALT_BYTES = 16
_NONCE_BYTES = 12
_KEY_BYTES = 32  # AES-256
_VAULT_FORMAT_VERSION = 2
_V1_FORMAT_VERSION = 1


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
        llm_timeout: Optional response timeout in seconds, used only by
            the local ``"ollama"`` provider. ``None`` means the default.
        session_cache: Arbitrary small key/value cache (e.g. the "template
            registry cache" from the spec) — not intended for large data.
    """

    llm_provider: str | None = None
    # Kept out of repr() so printing or logging a VaultData can't leak a key.
    llm_api_keys: dict[str, str] = field(default_factory=dict, repr=False)
    llm_model: str | None = None
    llm_host: str | None = None
    llm_timeout: float | None = None
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
            "llm_timeout": self.llm_timeout,
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
            llm_timeout=data.get("llm_timeout"),
            session_cache=dict(data.get("session_cache", {})),
        )


def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    """Derive a 256-bit AES key from a passphrase and salt via PBKDF2-HMAC-SHA256.

    Args:
        passphrase: The user-supplied vault passphrase.
        salt: A random per-vault salt.
        iterations: PBKDF2 iteration count. Callers pass it explicitly:
            the current setting when saving, or the file's own setting
            when loading.

    Returns:
        A 32-byte key suitable for AES-256-GCM.
    """
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=_KEY_BYTES, salt=salt, iterations=iterations)
    return kdf.derive(passphrase.encode("utf-8"))


def _associated_data(version: int, kdf_name: str, iterations: int, salt: bytes) -> bytes:
    """Build the AES-GCM associated data that authenticates a format 2 header.

    The bytes are rebuilt from the parsed values (compact JSON, sorted
    keys, salt re-encoded from its bytes), so whitespace or key order in
    the file doesn't matter, but changing any of the four values makes
    decryption fail.

    Args:
        version: The file format version.
        kdf_name: The key-derivation function's name.
        iterations: The KDF iteration count.
        salt: The KDF salt.

    Returns:
        The associated-data bytes.
    """
    header = {
        "version": version,
        "kdf": kdf_name,
        "iterations": iterations,
        "salt": base64.b64encode(salt).decode("ascii"),
    }
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode("ascii")


def _decode_b64(value: Any, length: int | None = None) -> bytes:
    """Strictly decode a base64 string from the vault file.

    Args:
        value: The value read from the file; must be a ``str``.
        length: If given, the exact number of bytes it must decode to.

    Returns:
        The decoded bytes.

    Raises:
        ValueError: If the value isn't a string, isn't valid base64, or
            decodes to the wrong length.
    """
    if not isinstance(value, str):
        raise ValueError("expected a base64 string")
    decoded = base64.b64decode(value, validate=True)
    if length is not None and len(decoded) != length:
        raise ValueError(f"expected {length} bytes, got {len(decoded)}")
    return decoded


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


def _fsync_directory(directory: Path) -> None:
    """Best-effort flush of a directory entry, so a rename survives a crash.

    Args:
        directory: The directory that holds the renamed file. No-op
            (never raises) where directories can't be opened (Windows).
    """
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _write_atomically(path: Path, content: str) -> None:
    """Replace ``path`` with ``content`` so a crash leaves the old or new file, never a partial one.

    Writes a temporary file in the same folder (created owner-only on
    POSIX), flushes it to disk, then renames it over ``path``. On Windows
    the rename is still atomic within a volume, but it fails if another
    process holds the file open, and file access comes from the folder's
    permissions rather than chmod.

    Args:
        path: The file to replace.
        content: The new contents.

    Raises:
        OSError: If any step fails; the temporary file is removed and
            ``path`` is left as it was.
    """
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            if hasattr(os, "fchmod"):
                os.fchmod(handle.fileno(), stat.S_IRUSR | stat.S_IWUSR)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    _fsync_directory(path.parent)


def save_vault(path: Path, passphrase: str, data: VaultData) -> None:
    """Encrypt and write vault data to disk in format 2, replacing any existing file.

    The write is atomic: a failure part-way leaves the previous vault
    intact. The file is owner read/write only on POSIX systems.

    Args:
        path: Destination vault file path.
        passphrase: Passphrase used to derive the encryption key.
        data: The vault contents to encrypt.

    Raises:
        VaultError: If the file cannot be written.
    """
    iterations = _KDF_ITERATIONS
    salt = os.urandom(_SALT_BYTES)
    nonce = os.urandom(_NONCE_BYTES)
    key = _derive_key(passphrase, salt, iterations)
    plaintext = json.dumps(data.to_dict()).encode("utf-8")
    associated_data = _associated_data(_VAULT_FORMAT_VERSION, _KDF_NAME, iterations, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, associated_data=associated_data)

    envelope = {
        "version": _VAULT_FORMAT_VERSION,
        "kdf": {
            "name": _KDF_NAME,
            "iterations": iterations,
            "salt": base64.b64encode(salt).decode("ascii"),
        },
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }
    try:
        _write_atomically(path, json.dumps(envelope))
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

    Reading never rewrites the file: a format 1 vault stays format 1
    until it is next saved.

    Raises:
        VaultError: If the file is missing or not a valid vault, uses a
            format version or key-derivation setting this version doesn't
            accept, or the passphrase is wrong or the file was changed
            (authentication tag mismatch).
    """
    context: dict[str, object] = {"path": str(path)}
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise VaultError(f"Vault file not found: {path}", context=context) from exc
    except OSError as exc:
        raise VaultError(f"Could not read vault file: {path}", context=context) from exc

    corrupted = f"Vault file is corrupted or not a QuestVector vault: {path}"
    try:
        envelope = json.loads(raw)
        version = envelope["version"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise VaultError(corrupted, context=context) from exc
    if isinstance(version, bool) or not isinstance(version, int):
        raise VaultError(corrupted, context=context)

    associated_data: bytes | None
    try:
        if version == _V1_FORMAT_VERSION:
            iterations = _V1_KDF_ITERATIONS
            salt = _decode_b64(envelope["salt"])
            associated_data = None
        elif version == _VAULT_FORMAT_VERSION:
            kdf = envelope["kdf"]
            kdf_name = kdf["name"]
            iterations = kdf["iterations"]
            salt = _decode_b64(kdf["salt"], _SALT_BYTES)
        else:
            raise VaultError(
                f"Vault format version {version} isn't supported by QuestVector "
                f"{__version__}; it may have been written by a newer version",
                context={**context, "version": version},
            )
        nonce = _decode_b64(envelope["nonce"], _NONCE_BYTES)
        ciphertext = _decode_b64(envelope["ciphertext"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VaultError(corrupted, context=context) from exc

    if version == _VAULT_FORMAT_VERSION:
        if kdf_name != _KDF_NAME:
            raise VaultError(
                f"Unsupported key derivation '{kdf_name}' in vault file: {path}",
                context=context,
            )
        # Checked before deriving anything, so a crafted count can't stall unlock.
        minimum, maximum = _MIN_KDF_ITERATIONS, _MAX_KDF_ITERATIONS
        if isinstance(iterations, bool) or not isinstance(iterations, int) or not (
            minimum <= iterations <= maximum
        ):
            raise VaultError(
                f"Vault key-derivation iteration count must be between {minimum:,} and "
                f"{maximum:,}; the file says {iterations!r}",
                context=context,
            )
        associated_data = _associated_data(version, kdf_name, iterations, salt)

    key = _derive_key(passphrase, salt, iterations)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, associated_data=associated_data)
    except InvalidTag as exc:
        raise VaultError(
            "Incorrect passphrase, or the vault file was changed or corrupted", context=context
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

    Saving always writes format 2, so this is where a format 1 vault is
    upgraded, with the passphrase the caller already supplied.

    Args:
        path: Vault file path.
        passphrase: Passphrase used for both decrypt and re-encrypt. Must
            be non-empty when the vault doesn't exist yet; an existing
            vault with an empty passphrase still opens and saves.
        mutate: A callable ``(VaultData) -> None`` that mutates the loaded
            data in place.

    Returns:
        The updated, now-persisted :class:`VaultData`.

    Raises:
        VaultError: If a new vault would get an empty passphrase, or
            propagated from :func:`load_vault` (for a wrong passphrase
            against an existing vault) or :func:`save_vault`.
    """
    if path.exists():
        data = load_vault(path, passphrase)
    elif not passphrase:
        raise VaultError("A new vault needs a non-empty passphrase", context={"path": str(path)})
    else:
        data = VaultData()
    mutate(data)
    save_vault(path, passphrase, data)
    return data
