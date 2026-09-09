"""Unit tests for questvector.core.vault."""

from __future__ import annotations

import base64
import json
import stat
import sys
from pathlib import Path

import pytest

from questvector.core.vault import VaultData, load_vault, save_vault, update_vault
from questvector.exceptions import VaultError


def test_save_and_load_vault_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    data = VaultData(llm_api_key="sk-test-123", session_cache={"foo": "bar"})

    save_vault(path, "correct-horse", data)
    loaded = load_vault(path, "correct-horse")

    assert loaded.llm_api_key == "sk-test-123"
    assert loaded.session_cache == {"foo": "bar"}


def test_load_vault_wrong_passphrase_raises_vault_error(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "correct-horse", VaultData(llm_api_key="secret"))

    with pytest.raises(VaultError):
        load_vault(path, "wrong-passphrase")


def test_load_vault_missing_file_raises_vault_error(tmp_path: Path) -> None:
    with pytest.raises(VaultError):
        load_vault(tmp_path / "nope.dat", "any-passphrase")


def test_load_vault_corrupted_json_raises_vault_error(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    path.write_text("not valid json at all", encoding="utf-8")
    with pytest.raises(VaultError):
        load_vault(path, "any-passphrase")


def test_load_vault_corrupted_ciphertext_raises_vault_error(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData(llm_api_key="secret"))

    # Deterministically flip one byte of the decoded ciphertext so the GCM
    # authentication tag can no longer verify, regardless of what random
    # bytes happened to land in this run's base64 encoding.
    envelope = json.loads(path.read_text(encoding="utf-8"))
    ciphertext = bytearray(base64.b64decode(envelope["ciphertext"]))
    ciphertext[0] ^= 0xFF
    envelope["ciphertext"] = base64.b64encode(bytes(ciphertext)).decode("ascii")
    path.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(VaultError):
        load_vault(path, "pass")


def test_update_vault_creates_new_vault_if_absent(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"

    def _set_key(data: VaultData) -> None:
        data.llm_api_key = "new-key"

    result = update_vault(path, "pass", _set_key)

    assert result.llm_api_key == "new-key"
    assert path.exists()


def test_update_vault_mutates_existing_vault(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData(session_cache={"a": 1}))

    def _add_key(data: VaultData) -> None:
        data.llm_api_key = "added-later"

    result = update_vault(path, "pass", _add_key)

    assert result.llm_api_key == "added-later"
    assert result.session_cache == {"a": 1}


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX file permissions only")
def test_save_vault_restricts_file_permissions(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData())

    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == stat.S_IRUSR | stat.S_IWUSR
