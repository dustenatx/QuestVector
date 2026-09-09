"""Unit tests for questvector.desktop.app.Api.

These exercise the JS/Python bridge logic directly -- no pywebview runtime,
window, or display server is created or required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from questvector.core import vault
from questvector.desktop.app import Api


def test_launch_workspace_returns_ok_envelope(tmp_path: Path) -> None:
    api = Api()
    response = api.launch_workspace(str(tmp_path / "ws"))
    assert response["ok"] is True
    assert "workspace_dir" in response["data"]


def test_launch_workspace_returns_error_envelope_on_failure(tmp_path: Path) -> None:
    file_path = tmp_path / "not-a-dir"
    file_path.write_text("x", encoding="utf-8")

    api = Api()
    response = api.launch_workspace(str(file_path))

    assert response["ok"] is False
    assert "error" in response


def test_get_dossier_returns_parsed_sections(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    api = Api()
    api.launch_workspace(str(workspace_dir))
    (workspace_dir / "Capabilities.md").write_text("## Cloud\n- AWS\n", encoding="utf-8")

    response = api.get_dossier(str(workspace_dir))

    assert response["ok"] is True
    assert response["data"]["capabilities"] == [{"domain": "Cloud", "text": "AWS"}]


def test_list_templates_returns_seven_starter_templates(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    api = Api()
    api.launch_workspace(str(workspace_dir))

    response = api.list_templates(str(workspace_dir))

    assert response["ok"] is True
    assert len(response["data"]) == 7


def test_sync_ast_returns_match_result(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    api = Api()
    api.launch_workspace(str(workspace_dir))
    (workspace_dir / "Capabilities.md").write_text(
        "## Cloud\n- AWS Terraform Kubernetes CI/CD\n", encoding="utf-8"
    )

    response = api.sync_ast(str(workspace_dir), "Looking for AWS Terraform Kubernetes", "devops-senior-mgr")

    assert response["ok"] is True
    assert "g_force_score" in response["data"]


def test_sync_ast_unknown_template_returns_error_envelope(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    api = Api()
    api.launch_workspace(str(workspace_dir))

    response = api.sync_ast(str(workspace_dir), "Some JD text", "does-not-exist")

    assert response["ok"] is False


def test_validate_template_returns_result_dict(tmp_path: Path) -> None:
    path = tmp_path / "t.yaml"
    path.write_text("categories:\n  - name: a\n    weight: 1.0\n", encoding="utf-8")

    api = Api()
    response = api.validate_template(str(path), False)

    assert response["ok"] is True
    assert response["data"]["valid"] is True


def test_export_bundle_writes_file(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    api = Api()
    api.launch_workspace(str(workspace_dir))

    response = api.export_bundle(str(workspace_dir), "resume", "pdf")

    assert response["ok"] is True
    assert Path(response["data"]["output_path"]).exists()


def test_set_llm_key_and_generate_narrative_error_without_key(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    api = Api()
    api.launch_workspace(str(workspace_dir))

    set_response = api.set_llm_key(str(workspace_dir), "pass", "")
    assert set_response["ok"] is True

    narrative_response = api.generate_narrative(str(workspace_dir), "some jd text", "pass")
    # No real API key was stored, so this must fail gracefully, not crash.
    assert narrative_response["ok"] is False


def test_generate_narrative_success_with_mocked_llm(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    api = Api()
    api.launch_workspace(str(workspace_dir))
    vault.save_vault(workspace_dir / ".questvector.vault", "pass", vault.VaultData(llm_api_key="sk-fake"))

    with patch("questvector.desktop.app.AnthropicNarrativeGenerator") as mock_generator_cls:
        mock_generator_cls.return_value.generate.return_value = "Generated summary."
        response = api.generate_narrative(str(workspace_dir), "some jd text", "pass")

    assert response["ok"] is True
    assert response["data"]["narrative"] == "Generated summary."
