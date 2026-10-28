"""Unit tests for questvector.core.vault."""

from __future__ import annotations

import base64
import json
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from questvector.core import vault
from questvector.core.vault import VaultData, load_vault, save_vault, update_vault
from questvector.exceptions import VaultError

V1_FIXTURES = Path(__file__).parent / "fixtures" / "vault"
V1_PASSPHRASE = "qv-fixture-v1-passphrase"


def test_save_and_load_vault_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    data = VaultData(
        llm_provider="anthropic",
        llm_api_keys={"anthropic": "sk-test-123"},
        session_cache={"foo": "bar"},
    )

    save_vault(path, "correct-horse", data)
    loaded = load_vault(path, "correct-horse")

    assert loaded.llm_provider == "anthropic"
    assert loaded.api_key_for("anthropic") == "sk-test-123"
    assert loaded.session_cache == {"foo": "bar"}


def test_vault_data_stores_multiple_provider_keys_side_by_side(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    data = VaultData(
        llm_provider="openai",
        llm_api_keys={"anthropic": "sk-ant", "openai": "sk-oai"},
        llm_model="gpt-4o-mini",
    )

    save_vault(path, "pass", data)
    loaded = load_vault(path, "pass")

    assert loaded.llm_provider == "openai"
    assert loaded.api_key_for("openai") == "sk-oai"
    assert loaded.api_key_for("anthropic") == "sk-ant"
    assert loaded.api_key_for("gemini") is None
    assert loaded.llm_model == "gpt-4o-mini"


def test_vault_data_ollama_needs_no_api_key(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    data = VaultData(llm_provider="ollama", llm_model="llama3.1", llm_host="http://localhost:11434")

    save_vault(path, "pass", data)
    loaded = load_vault(path, "pass")

    assert loaded.llm_provider == "ollama"
    assert loaded.api_key_for("ollama") is None
    assert loaded.llm_host == "http://localhost:11434"


def test_vault_data_round_trips_llm_timeout(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"

    save_vault(path, "pass", VaultData(llm_provider="ollama", llm_timeout=600.0))

    assert load_vault(path, "pass").llm_timeout == 600.0


def test_from_dict_without_llm_timeout_uses_default() -> None:
    # Vault files written before the timeout setting existed have no key.
    data = VaultData.from_dict({"llm_provider": "ollama", "llm_model": "llama3.1"})

    assert data.llm_timeout is None


def test_from_dict_migrates_legacy_single_key_schema() -> None:
    # Pre-multi-provider vault files stored a bare ``llm_api_key`` string,
    # always for Anthropic (the only provider that existed at the time).
    legacy = {"llm_api_key": "sk-legacy", "session_cache": {"a": 1}}

    migrated = VaultData.from_dict(legacy)

    assert migrated.llm_provider == "anthropic"
    assert migrated.api_key_for("anthropic") == "sk-legacy"
    assert migrated.session_cache == {"a": 1}


def test_load_vault_wrong_passphrase_raises_vault_error(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "correct-horse", VaultData(llm_provider="anthropic", llm_api_keys={"anthropic": "secret"}))

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
    save_vault(path, "pass", VaultData(llm_provider="anthropic", llm_api_keys={"anthropic": "secret"}))

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
        data.llm_provider = "anthropic"
        data.llm_api_keys["anthropic"] = "new-key"

    result = update_vault(path, "pass", _set_key)

    assert result.api_key_for("anthropic") == "new-key"
    assert path.exists()


def test_update_vault_mutates_existing_vault(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData(session_cache={"a": 1}))

    def _add_key(data: VaultData) -> None:
        data.llm_provider = "anthropic"
        data.llm_api_keys["anthropic"] = "added-later"

    result = update_vault(path, "pass", _add_key)

    assert result.api_key_for("anthropic") == "added-later"
    assert result.session_cache == {"a": 1}


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX file permissions only")
def test_save_vault_restricts_file_permissions(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData())

    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == stat.S_IRUSR | stat.S_IWUSR


# --- Format 2: settings recorded and authenticated (ADR-0015) ---------------


def _envelope(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _write_envelope(path: Path, envelope: dict[str, Any]) -> None:
    path.write_text(json.dumps(envelope), encoding="utf-8")


def test_fast_kdf_fixture_is_in_effect(tmp_path: Path) -> None:
    # Proves vault.py reads the iteration settings at call time: the
    # autouse fixture in conftest.py patched them, and the file shows it.
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData(llm_provider="ollama"))

    assert _envelope(path)["kdf"]["iterations"] == 1_000
    assert load_vault(path, "pass").llm_provider == "ollama"


@pytest.mark.real_kdf
def test_shipped_kdf_settings() -> None:
    assert vault._KDF_NAME == "pbkdf2-hmac-sha256"
    assert vault._KDF_ITERATIONS == 1_000_000
    assert vault._MIN_KDF_ITERATIONS == 600_000
    assert vault._MAX_KDF_ITERATIONS == 5_000_000
    assert vault._V1_KDF_ITERATIONS == 390_000
    assert vault._VAULT_FORMAT_VERSION == 2


@pytest.mark.real_kdf
def test_real_kdf_round_trip_writes_format_2(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "correct-horse", VaultData(llm_provider="ollama", llm_model="llama3.1"))

    envelope = _envelope(path)
    assert envelope["version"] == 2
    assert envelope["kdf"]["name"] == "pbkdf2-hmac-sha256"
    assert envelope["kdf"]["iterations"] == 1_000_000
    assert len(base64.b64decode(envelope["kdf"]["salt"])) == 16
    assert len(base64.b64decode(envelope["nonce"])) == 12
    assert set(envelope) == {"version", "kdf", "nonce", "ciphertext"}
    assert load_vault(path, "correct-horse").llm_model == "llama3.1"


@pytest.mark.real_kdf
@pytest.mark.parametrize("iterations", [599_999, 5_000_001, 0, -1])
def test_load_rejects_iterations_out_of_range_before_deriving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, iterations: int
) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData())
    envelope = _envelope(path)
    envelope["kdf"]["iterations"] = iterations
    _write_envelope(path, envelope)

    def _must_not_derive(*_args: object) -> bytes:
        raise AssertionError("key derived for an out-of-range iteration count")

    monkeypatch.setattr(vault, "_derive_key", _must_not_derive)

    with pytest.raises(VaultError, match="between 600,000 and 5,000,000"):
        load_vault(path, "pass")


@pytest.mark.parametrize("iterations", ["1000", 1000.0, True, None])
def test_load_rejects_non_integer_iterations(tmp_path: Path, iterations: object) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData())
    envelope = _envelope(path)
    envelope["kdf"]["iterations"] = iterations
    _write_envelope(path, envelope)

    with pytest.raises(VaultError):
        load_vault(path, "pass")


def test_header_is_authenticated_as_associated_data(tmp_path: Path) -> None:
    # Decrypting with the right key but without the header as associated
    # data must fail, which shows the header is bound to the ciphertext.
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData(llm_provider="ollama"))
    envelope = _envelope(path)
    salt = base64.b64decode(envelope["kdf"]["salt"])
    nonce = base64.b64decode(envelope["nonce"])
    ciphertext = base64.b64decode(envelope["ciphertext"])
    key = vault._derive_key("pass", salt, envelope["kdf"]["iterations"])

    with pytest.raises(InvalidTag):
        AESGCM(key).decrypt(nonce, ciphertext, associated_data=None)
    aad = vault._associated_data(2, "pbkdf2-hmac-sha256", envelope["kdf"]["iterations"], salt)
    assert json.loads(AESGCM(key).decrypt(nonce, ciphertext, aad))["llm_provider"] == "ollama"


@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param(lambda e: e["kdf"].__setitem__("iterations", e["kdf"]["iterations"] + 1), id="iterations"),
        pytest.param(
            lambda e: e["kdf"].__setitem__("salt", base64.b64encode(b"\x00" * 16).decode("ascii")), id="salt"
        ),
        pytest.param(lambda e: e["kdf"].__setitem__("name", "pbkdf2-hmac-sha512"), id="kdf-name"),
        pytest.param(lambda e: e.__setitem__("version", 1), id="version"),
    ],
)
def test_changing_any_header_field_fails(tmp_path: Path, tamper: Any) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData(llm_provider="ollama"))
    envelope = _envelope(path)
    tamper(envelope)
    _write_envelope(path, envelope)

    with pytest.raises(VaultError):
        load_vault(path, "pass")


def test_header_whitespace_and_key_order_do_not_matter(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData(llm_provider="ollama"))
    envelope = _envelope(path)
    reordered = {
        "ciphertext": envelope["ciphertext"],
        "nonce": envelope["nonce"],
        "kdf": dict(reversed(list(envelope["kdf"].items()))),
        "version": envelope["version"],
    }
    path.write_text(json.dumps(reordered, indent=4), encoding="utf-8")

    assert load_vault(path, "pass").llm_provider == "ollama"


@pytest.mark.parametrize(
    ("version", "message"),
    [
        (3, "Vault format version 3 isn't supported by QuestVector"),
        ("2", "corrupted or not a QuestVector vault"),
        (True, "corrupted or not a QuestVector vault"),
    ],
)
def test_load_rejects_unknown_or_malformed_versions(tmp_path: Path, version: object, message: str) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData())
    envelope = _envelope(path)
    envelope["version"] = version
    _write_envelope(path, envelope)

    with pytest.raises(VaultError, match=message):
        load_vault(path, "pass")


def test_load_rejects_missing_version(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData())
    envelope = _envelope(path)
    del envelope["version"]
    _write_envelope(path, envelope)

    with pytest.raises(VaultError, match="corrupted or not a QuestVector vault"):
        load_vault(path, "pass")


@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param(lambda e: e["kdf"].__setitem__("salt", "not base64!"), id="salt-not-base64"),
        pytest.param(lambda e: e["kdf"].__setitem__("salt", base64.b64encode(b"short").decode()), id="salt-length"),
        pytest.param(lambda e: e.__setitem__("nonce", base64.b64encode(b"short").decode()), id="nonce-length"),
        pytest.param(lambda e: e.__delitem__("kdf"), id="kdf-missing"),
        pytest.param(lambda e: e.__setitem__("kdf", ["pbkdf2-hmac-sha256"]), id="kdf-not-object"),
    ],
)
def test_load_rejects_malformed_header(tmp_path: Path, tamper: Any) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData())
    envelope = _envelope(path)
    tamper(envelope)
    _write_envelope(path, envelope)

    with pytest.raises(VaultError, match="corrupted or not a QuestVector vault"):
        load_vault(path, "pass")


def test_vault_data_repr_hides_api_keys() -> None:
    data = VaultData(llm_provider="anthropic", llm_api_keys={"anthropic": "QVREPR-not-a-real-key"})

    assert "QVREPR-not-a-real-key" not in repr(data)
    assert "anthropic" in repr(data)


# --- Format 1 vaults written by QuestVector 1.1.0 ----------------------------


@pytest.mark.real_kdf
def test_v1_fixture_opens(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    shutil.copy(V1_FIXTURES / "v1-vault.json", path)

    loaded = load_vault(path, V1_PASSPHRASE)

    assert _envelope(path)["version"] == 1
    assert loaded.llm_provider == "anthropic"
    assert loaded.api_key_for("anthropic") == "QVFIXTURE-v1-not-a-real-key"
    assert loaded.session_cache == {"a": 1}


@pytest.mark.real_kdf
def test_v1_fixture_reading_does_not_rewrite_it(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    shutil.copy(V1_FIXTURES / "v1-vault.json", path)
    before = path.read_bytes()

    load_vault(path, V1_PASSPHRASE)

    assert path.read_bytes() == before


@pytest.mark.real_kdf
def test_v1_fixture_wrong_passphrase_raises_vault_error(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    shutil.copy(V1_FIXTURES / "v1-vault.json", path)

    with pytest.raises(VaultError, match="Incorrect passphrase"):
        load_vault(path, "wrong-passphrase")


@pytest.mark.real_kdf
def test_v1_fixture_is_upgraded_to_format_2_on_save(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    shutil.copy(V1_FIXTURES / "v1-vault.json", path)

    def _set_model(data: VaultData) -> None:
        data.llm_model = "claude-test-model"

    update_vault(path, V1_PASSPHRASE, _set_model)

    envelope = _envelope(path)
    assert envelope["version"] == 2
    assert envelope["kdf"] == {
        "name": "pbkdf2-hmac-sha256",
        "iterations": 1_000_000,
        "salt": envelope["kdf"]["salt"],
    }
    assert "salt" not in envelope
    reloaded = load_vault(path, V1_PASSPHRASE)
    assert reloaded.api_key_for("anthropic") == "QVFIXTURE-v1-not-a-real-key"
    assert reloaded.session_cache == {"a": 1}
    assert reloaded.llm_model == "claude-test-model"


@pytest.mark.real_kdf
def test_v1_fixture_with_empty_passphrase_opens_and_upgrades(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    shutil.copy(V1_FIXTURES / "v1-vault-empty-passphrase.json", path)

    assert load_vault(path, "").llm_model == "llama3.1"
    update_vault(path, "", lambda data: None)

    assert _envelope(path)["version"] == 2
    assert load_vault(path, "").llm_provider == "ollama"


# --- Empty passphrases ---------------------------------------------------------


def test_update_vault_rejects_empty_passphrase_for_new_vault(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"

    with pytest.raises(VaultError, match="A new vault needs a non-empty passphrase"):
        update_vault(path, "", lambda data: None)
    assert not path.exists()


def test_update_vault_accepts_empty_passphrase_for_existing_vault(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "", VaultData())

    def _set_provider(data: VaultData) -> None:
        data.llm_provider = "ollama"

    update_vault(path, "", _set_provider)

    assert load_vault(path, "").llm_provider == "ollama"


# --- Atomic save ---------------------------------------------------------------


def _leftover_temp_files(directory: Path) -> list[Path]:
    return [p for p in directory.iterdir() if p.name.endswith(".tmp")]


@pytest.mark.parametrize("failing", ["replace", "fsync"])
def test_failed_save_leaves_previous_vault_intact(tmp_path: Path, failing: str) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData(llm_provider="ollama", llm_model="before"))
    before = path.read_bytes()

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated failure mid-save")

    # A separate context, so undoing it leaves the fast-KDF fixture in place.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(vault.os, failing, _fail)
        with pytest.raises(VaultError, match="Could not write vault file"):
            save_vault(path, "pass", VaultData(llm_provider="ollama", llm_model="after"))

    assert path.read_bytes() == before
    assert load_vault(path, "pass").llm_model == "before"
    assert _leftover_temp_files(tmp_path) == []


def test_successful_save_leaves_no_temp_file(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData())
    save_vault(path, "pass", VaultData(llm_provider="ollama"))

    assert _leftover_temp_files(tmp_path) == []
    assert [p.name for p in tmp_path.iterdir()] == ["vault.dat"]


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX file permissions only")
def test_save_over_world_readable_vault_restores_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "vault.dat"
    save_vault(path, "pass", VaultData())
    os.chmod(path, 0o644)

    save_vault(path, "pass", VaultData(llm_provider="ollama"))

    assert stat.S_IMODE(path.stat().st_mode) == stat.S_IRUSR | stat.S_IWUSR
