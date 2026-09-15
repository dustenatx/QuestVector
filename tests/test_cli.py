"""Unit tests for questvector.cli (the `qv` command-line interface)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from questvector import __version__, cli
from questvector.core import vault


def test_version_flag_prints_version_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--version"])

    assert exc_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_installed_package_version_matches_dunder_version() -> None:
    # pyproject.toml sources its packaging version from questvector.__version__
    # (see [tool.setuptools.dynamic]) rather than duplicating the string --
    # this guards against the two silently drifting apart again.
    import importlib.metadata

    assert importlib.metadata.version("questvector") == __version__


def test_launch_creates_workspace(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace_dir = tmp_path / "ws"
    exit_code = cli.main(["launch", "--dir", str(workspace_dir), "--json"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["workspace_dir"] == str(workspace_dir)
    assert (workspace_dir / "Capabilities.md").exists()


def test_sync_ast_scores_job_description(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace_dir = tmp_path / "ws"
    cli.main(["launch", "--dir", str(workspace_dir)])
    (workspace_dir / "Capabilities.md").write_text(
        "## Cloud\n- AWS Terraform Kubernetes automation and CI/CD pipelines\n",
        encoding="utf-8",
    )
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Looking for AWS Terraform Kubernetes CI/CD experience", encoding="utf-8")
    capsys.readouterr()

    exit_code = cli.main(
        [
            "sync-ast",
            "--dir",
            str(workspace_dir),
            "--target",
            str(jd_path),
            "--template",
            "devops-senior-mgr",
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert 0.0 <= output["g_force_score"] <= 100.0
    assert "alert_level" in output


def test_sync_ast_unknown_template_returns_error_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace_dir = tmp_path / "ws"
    cli.main(["launch", "--dir", str(workspace_dir)])
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Some job description", encoding="utf-8")

    exit_code = cli.main(
        ["sync-ast", "--dir", str(workspace_dir), "--target", str(jd_path), "--template", "nonexistent"]
    )

    assert exit_code == 1
    assert "ERROR" in capsys.readouterr().err


def test_export_produces_pdf_bundle(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    cli.main(["launch", "--dir", str(workspace_dir)])

    exit_code = cli.main(
        ["export", "--dir", str(workspace_dir), "--bundle", "my-resume", "--format", "pdf"]
    )

    assert exit_code == 0
    assert (workspace_dir / "bundles" / "my-resume.pdf").exists()


def test_template_validate_fix_persists_and_returns_zero(tmp_path: Path) -> None:
    template_path = tmp_path / "bad.yaml"
    template_path.write_text(
        "categories:\n  - name: a\n    weight: 0.3\n  - name: b\n    weight: 0.3\n", encoding="utf-8"
    )

    exit_code = cli.main(["template", "validate", str(template_path), "--fix"])

    assert exit_code == 0


def test_template_validate_without_fix_returns_one_when_invalid(tmp_path: Path) -> None:
    template_path = tmp_path / "bad.yaml"
    template_path.write_text(
        "categories:\n  - name: a\n    weight: 0.3\n  - name: b\n    weight: 0.3\n", encoding="utf-8"
    )

    exit_code = cli.main(["template", "validate", str(template_path)])

    assert exit_code == 1


def test_launch_human_readable_output_lists_created_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace_dir = tmp_path / "ws"
    exit_code = cli.main(["launch", "--dir", str(workspace_dir)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Workspace initialized" in out
    assert "Capabilities.md" in out


def test_sync_ast_human_readable_output_shows_gaps(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace_dir = tmp_path / "ws"
    cli.main(["launch", "--dir", str(workspace_dir)])
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Needs Kubernetes and Terraform at a senior level", encoding="utf-8")
    capsys.readouterr()

    exit_code = cli.main(
        ["sync-ast", "--dir", str(workspace_dir), "--target", str(jd_path), "--template", "devops-senior-mgr"]
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "G-Force Match" in out


def test_export_with_narrative_calls_llm_generator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace_dir = tmp_path / "ws"
    cli.main(["launch", "--dir", str(workspace_dir)])
    (workspace_dir / "Capabilities.md").write_text("## Cloud\n- AWS Terraform\n", encoding="utf-8")
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Looking for AWS Terraform experience", encoding="utf-8")
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: "pass")
    vault.save_vault(
        workspace_dir / ".questvector.vault",
        "pass",
        vault.VaultData(llm_provider="anthropic", llm_api_keys={"anthropic": "sk-fake"}),
    )

    with patch("questvector.core.llm.AnthropicNarrativeGenerator") as mock_generator_cls:
        mock_generator_cls.return_value.generate.return_value = "Generated narrative text."
        exit_code = cli.main(
            [
                "export",
                "--dir",
                str(workspace_dir),
                "--bundle",
                "resume",
                "--format",
                "pdf",
                "--target",
                str(jd_path),
                "--template",
                "devops-senior-mgr",
                "--narrative",
            ]
        )

    assert exit_code == 0
    assert (workspace_dir / "bundles" / "resume.pdf").exists()


def test_vault_set_key_stores_encrypted_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()
    responses = iter(["my-passphrase", "sk-my-api-key"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_args, **_kwargs: next(responses))

    exit_code = cli.main(["vault", "set-key", "--dir", str(workspace_dir), "--provider", "anthropic"])

    assert exit_code == 0
    loaded = vault.load_vault(workspace_dir / ".questvector.vault", "my-passphrase")
    assert loaded.llm_provider == "anthropic"
    assert loaded.api_key_for("anthropic") == "sk-my-api-key"


def test_vault_set_key_ollama_needs_no_api_key_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()
    # Only the vault passphrase should be requested -- a second call would
    # mean the CLI wrongly prompted for an API key Ollama doesn't need.
    responses = iter(["my-passphrase"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_args, **_kwargs: next(responses))

    exit_code = cli.main(
        ["vault", "set-key", "--dir", str(workspace_dir), "--provider", "ollama", "--model", "llama3.1"]
    )

    assert exit_code == 0
    loaded = vault.load_vault(workspace_dir / ".questvector.vault", "my-passphrase")
    assert loaded.llm_provider == "ollama"
    assert loaded.llm_model == "llama3.1"
    assert loaded.api_key_for("ollama") is None


def test_vault_set_key_unknown_provider_rejected_by_argparse(tmp_path: Path) -> None:
    # --provider is constrained to PROVIDERS via argparse `choices`, so an
    # unknown value never reaches _cmd_vault_set_key's own guard clause.
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()

    with pytest.raises(SystemExit):
        cli.main(["vault", "set-key", "--dir", str(workspace_dir), "--provider", "not-a-real-provider"])
