"""Secrets never leak (PRD R16).

The stored API key and the vault passphrase must never appear in command
output, error messages, logs, exported bundles, or the vault file's bytes.
Each test runs a real CLI or desktop-bridge flow with synthetic markers and
searches everything the flow produced for them.

The markers are deliberately plain words with no provider prefix, so secret
scanners such as gitleaks don't mistake them for real keys.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import logging
import re
import zipfile
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from questvector import cli
from questvector.core import vault
from questvector.core.llm import _redact
from questvector.desktop.app import Api
from questvector.exceptions import QuestVectorError

API_KEY_MARKER = "QVLEAKMARKER-apikey-not-a-real-key"
PASSPHRASE_MARKER = "QVLEAKMARKER-passphrase-not-real"
MARKERS = (API_KEY_MARKER, PASSPHRASE_MARKER)
VAULT_FILE = ".questvector.vault"


def _sdk_installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


requires_anthropic = pytest.mark.skipif(not _sdk_installed("anthropic"), reason="anthropic SDK not installed")
requires_openai = pytest.mark.skipif(not _sdk_installed("openai"), reason="openai SDK not installed")
requires_gemini = pytest.mark.skipif(not _sdk_installed("google.genai"), reason="google-genai SDK not installed")


@pytest.fixture(autouse=True)
def _capture_all_logs(caplog: pytest.LogCaptureFixture) -> None:
    """Record every log record, at every level, from every logger."""
    caplog.set_level(logging.DEBUG)


@pytest.fixture(autouse=True)
def _no_plain_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail if anything prompts with input(), which echoes what is typed."""

    def _input(*_args: object) -> str:
        raise AssertionError("input() was called; secrets must be read with getpass")

    monkeypatch.setattr("builtins.input", _input)


def _assert_clean(text: str, where: str) -> None:
    for marker in MARKERS:
        assert marker not in text, f"{marker} leaked into {where}"


def _assert_flow_clean(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> str:
    """Check stdout, stderr and logs; return stdout + stderr for further checks."""
    captured = capsys.readouterr()
    _assert_clean(captured.out, "stdout")
    _assert_clean(captured.err, "stderr")
    _assert_clean(caplog.text, "logs")
    return captured.out + captured.err


def _decode_pdf_stream(data: bytes) -> bytes:
    """Undo ReportLab's stream filters: ASCII85 (ending in ``~>``) then Flate."""
    data = data.strip()
    if data.endswith(b"~>"):
        data = base64.a85decode(data[:-2].removeprefix(b"<~"))
    return zlib.decompress(data)


def _pdf_text(path: Path) -> str:
    """Return a PDF's raw bytes plus every stream, decoded."""
    raw = path.read_bytes()
    parts = [raw.decode("latin-1")]
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
        try:
            parts.append(_decode_pdf_stream(match.group(1)).decode("latin-1"))
        except (zlib.error, ValueError):
            continue  # a stream with another filter (none in ReportLab's text output)
    return "\n".join(parts)


def _docx_text(path: Path) -> str:
    """Return the text of every part inside a DOCX (zip) file."""
    with zipfile.ZipFile(path) as archive:
        return "\n".join(archive.read(name).decode("utf-8", "replace") for name in archive.namelist())


def _set_key(workspace_dir: Path, monkeypatch: pytest.MonkeyPatch, provider: str = "anthropic") -> int:
    """Run `qv vault set-key` for a new vault with the markers as passphrase and key."""
    answers = iter([PASSPHRASE_MARKER, PASSPHRASE_MARKER, API_KEY_MARKER])
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: next(answers))
    return cli.main(["vault", "set-key", "--dir", str(workspace_dir), "--provider", provider])


@pytest.fixture()
def workspace_with_jd(tmp_path: Path) -> tuple[Path, Path]:
    workspace_dir = tmp_path / "ws"
    cli.main(["launch", "--dir", str(workspace_dir)])
    (workspace_dir / "Capabilities.md").write_text("## Cloud\n- AWS Terraform\n", encoding="utf-8")
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Looking for AWS Terraform experience", encoding="utf-8")
    return workspace_dir, jd_path


def test_set_key_output_logs_and_vault_file_hold_no_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()

    assert _set_key(workspace_dir, monkeypatch) == 0

    output = _assert_flow_clean(capsys, caplog)
    assert "stored in encrypted vault" in output
    vault_bytes = (workspace_dir / VAULT_FILE).read_bytes()
    for marker in MARKERS:
        assert marker.encode() not in vault_bytes
    # The key really is in there, encrypted.
    loaded = vault.load_vault(workspace_dir / VAULT_FILE, PASSPHRASE_MARKER)
    assert loaded.api_key_for("anthropic") == API_KEY_MARKER


@pytest.mark.parametrize("fmt", ["pdf", "docx"])
def test_export_with_narrative_leaks_nothing(
    workspace_with_jd: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    fmt: str,
) -> None:
    workspace_dir, jd_path = workspace_with_jd
    assert _set_key(workspace_dir, monkeypatch) == 0
    capsys.readouterr()
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: PASSPHRASE_MARKER)

    with patch("questvector.core.llm.AnthropicNarrativeGenerator") as generator_cls:
        generator_cls.return_value.generate.return_value = "Generated narrative text."
        exit_code = cli.main(
            [
                "export", "--dir", str(workspace_dir), "--bundle", "resume", "--format", fmt,
                "--target", str(jd_path), "--template", "devops-senior-mgr", "--narrative",
            ]
        )

    assert exit_code == 0
    # The generator was given the key, so it really was read from the vault.
    assert generator_cls.call_args.args[0] == API_KEY_MARKER
    _assert_flow_clean(capsys, caplog)
    bundle = workspace_dir / "bundles" / f"resume.{fmt}"
    text = _pdf_text(bundle) if fmt == "pdf" else _docx_text(bundle)
    # Positive control: the decoding works, so a missing marker means something.
    assert "Generated narrative text" in text
    _assert_clean(text, f"the exported {fmt} bundle")


def _cli_error(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture, argv: list[str]) -> str:
    assert cli.main(argv) == 1
    output = _assert_flow_clean(capsys, caplog)
    assert "[QV] ERROR:" in output
    return output


def test_wrong_passphrase_error_leaks_nothing(
    workspace_with_jd: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    workspace_dir, _jd_path = workspace_with_jd
    assert _set_key(workspace_dir, monkeypatch) == 0
    capsys.readouterr()
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: PASSPHRASE_MARKER + "-wrong")

    output = _cli_error(capsys, caplog, ["vault", "set-key", "--dir", str(workspace_dir), "--provider", "ollama"])

    assert "Incorrect passphrase" in output
    api_response = Api().set_llm_key(str(workspace_dir), PASSPHRASE_MARKER + "-wrong", "ollama")
    assert api_response["ok"] is False
    _assert_clean(api_response["error"], "the desktop error")


def test_tampered_vault_error_leaks_nothing(
    workspace_with_jd: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    workspace_dir, jd_path = workspace_with_jd
    assert _set_key(workspace_dir, monkeypatch) == 0
    capsys.readouterr()
    path = workspace_dir / VAULT_FILE
    envelope = json.loads(path.read_text(encoding="utf-8"))
    ciphertext = bytearray(base64.b64decode(envelope["ciphertext"]))
    ciphertext[0] ^= 0xFF
    envelope["ciphertext"] = base64.b64encode(bytes(ciphertext)).decode("ascii")
    path.write_text(json.dumps(envelope), encoding="utf-8")
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: PASSPHRASE_MARKER)

    output = _cli_error(
        capsys,
        caplog,
        [
            "export", "--dir", str(workspace_dir), "--bundle", "resume", "--format", "pdf",
            "--target", str(jd_path), "--template", "devops-senior-mgr", "--narrative",
        ],
    )

    assert "changed or corrupted" in output
    api_response = Api().generate_narrative(str(workspace_dir), "AWS Terraform", PASSPHRASE_MARKER)
    assert api_response["ok"] is False
    _assert_clean(api_response["error"], "the desktop error")


def test_no_provider_configured_error_leaks_nothing(
    workspace_with_jd: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    workspace_dir, jd_path = workspace_with_jd
    vault.save_vault(workspace_dir / VAULT_FILE, PASSPHRASE_MARKER, vault.VaultData())
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: PASSPHRASE_MARKER)

    output = _cli_error(
        capsys,
        caplog,
        [
            "export", "--dir", str(workspace_dir), "--bundle", "resume", "--format", "pdf",
            "--target", str(jd_path), "--template", "devops-senior-mgr", "--narrative",
        ],
    )

    assert "No LLM provider configured" in output
    api_response = Api().generate_narrative(str(workspace_dir), "AWS Terraform", PASSPHRASE_MARKER)
    assert api_response["ok"] is False
    _assert_clean(api_response["error"], "the desktop error")


def test_new_vault_passphrase_errors_leak_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()
    answers = iter([PASSPHRASE_MARKER, PASSPHRASE_MARKER + "-typo"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: next(answers))

    output = _cli_error(capsys, caplog, ["vault", "set-key", "--dir", str(workspace_dir), "--provider", "anthropic"])

    assert "Passphrases don't match" in output
    api_response = Api().set_llm_key(str(workspace_dir), "", "anthropic", API_KEY_MARKER)
    assert api_response["ok"] is False
    assert "non-empty passphrase" in api_response["error"]
    _assert_clean(api_response["error"], "the desktop error")
    assert not (workspace_dir / VAULT_FILE).exists()


def _sdk_error_mentioning_key(provider: str) -> Exception:
    """Build each SDK's own error type, with the key in its message."""
    message = f"Invalid credentials: {API_KEY_MARKER}"
    if provider == "anthropic":
        import anthropic

        return anthropic.APIError(message=message, request=MagicMock(), body=None)
    if provider == "openai":
        import openai

        return openai.APIError(message=message, request=MagicMock(), body=None)
    from google.genai import errors as genai_errors

    return genai_errors.APIError(401, {"error": {"message": message}})


@pytest.mark.parametrize(
    ("provider", "client_path", "call"),
    [
        pytest.param("anthropic", "anthropic.Anthropic", "messages.create", marks=requires_anthropic),
        pytest.param("openai", "openai.OpenAI", "chat.completions.create", marks=requires_openai),
        pytest.param("gemini", "google.genai.Client", "models.generate_content", marks=requires_gemini),
    ],
)
def test_sdk_error_that_echoes_the_key_is_redacted(
    workspace_with_jd: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    provider: str,
    client_path: str,
    call: str,
) -> None:
    workspace_dir, jd_path = workspace_with_jd
    assert _set_key(workspace_dir, monkeypatch, provider) == 0
    capsys.readouterr()
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: PASSPHRASE_MARKER)
    sdk_error = _sdk_error_mentioning_key(provider)
    assert API_KEY_MARKER in str(sdk_error)  # the SDK error really does echo it

    with patch(client_path) as client_cls:
        method = client_cls.return_value
        for attribute in call.split("."):
            method = getattr(method, attribute)
        method.side_effect = sdk_error
        output = _cli_error(
            capsys,
            caplog,
            [
                "export", "--dir", str(workspace_dir), "--bundle", "resume", "--format", "pdf",
                "--target", str(jd_path), "--template", "devops-senior-mgr", "--narrative",
            ],
        )
        api_response = Api().generate_narrative(str(workspace_dir), "AWS Terraform", PASSPHRASE_MARKER)

    assert "LLM API call failed" in output
    assert "[redacted]" in output
    assert api_response["ok"] is False
    assert "[redacted]" in api_response["error"]
    _assert_clean(api_response["error"], "the desktop error")


def test_redact_replaces_every_occurrence() -> None:
    text = f"bad key {API_KEY_MARKER}; retried with {API_KEY_MARKER}"

    assert _redact(text, API_KEY_MARKER) == "bad key [redacted]; retried with [redacted]"
    assert _redact(text, "") == text


def test_vault_data_repr_and_vault_errors_hold_no_secrets(tmp_path: Path) -> None:
    data = vault.VaultData(llm_provider="anthropic", llm_api_keys={"anthropic": API_KEY_MARKER})
    _assert_clean(repr(data), "repr(VaultData)")

    path = tmp_path / VAULT_FILE
    vault.save_vault(path, PASSPHRASE_MARKER, data)
    errors: list[QuestVectorError] = []
    for attempt in (
        lambda: vault.load_vault(path, PASSPHRASE_MARKER + "-wrong"),
        lambda: vault.load_vault(tmp_path / "missing", PASSPHRASE_MARKER),
        lambda: vault.update_vault(tmp_path / "new", "", lambda _d: None),
    ):
        with pytest.raises(QuestVectorError) as excinfo:
            attempt()
        errors.append(excinfo.value)

    for error in errors:
        _assert_clean(str(error), f"str({type(error).__name__})")
        _assert_clean(repr(error), f"repr({type(error).__name__})")
