"""Checks on the GitHub Actions workflow files.

Every workflow pins its actions to a commit SHA with a version comment and
keeps the checkout token out of the working copy (ADR-0011). The release
workflow runs only on v* tags, and only its release job can write
(ADR-0014). Comments are lost when YAML is parsed, so the pin check reads
the raw text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).parent.parent / ".github" / "workflows"
WORKFLOW_FILES = sorted(WORKFLOWS.glob("*.yml"))
USES_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)(.*)$")
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
VERSION_COMMENT = re.compile(r"^\s+# v\d+\.\d+\.\d+$")


def _load(path: Path) -> dict[Any, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _steps(workflow: dict[Any, Any]) -> list[dict[str, Any]]:
    return [step for job in workflow["jobs"].values() for step in job.get("steps", [])]


def test_workflow_files_found() -> None:
    assert WORKFLOWS / "release.yml" in WORKFLOW_FILES


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_actions_pinned_to_sha_with_version_comment(path: Path) -> None:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = USES_LINE.match(line)
        if match:
            ref, rest = match.groups()
            assert PINNED.match(ref), f"{path.name}:{number}: {ref} is not pinned to a commit SHA"
            assert VERSION_COMMENT.match(rest), f"{path.name}:{number}: missing '# vX.Y.Z' comment"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_checkout_does_not_persist_credentials(path: Path) -> None:
    for step in _steps(_load(path)):
        if str(step.get("uses", "")).startswith("actions/checkout@"):
            assert step.get("with", {}).get("persist-credentials") is False, path.name


def test_release_runs_only_on_version_tags() -> None:
    workflow = _load(WORKFLOWS / "release.yml")
    # PyYAML reads the bare key `on` as the boolean True (YAML 1.1).
    assert workflow[True] == {"push": {"tags": ["v*"]}}


def test_release_permissions() -> None:
    workflow = _load(WORKFLOWS / "release.yml")
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["build"]["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["release"]["permissions"] == {
        "contents": "write",
        "id-token": "write",
        "attestations": "write",
    }


def test_release_job_runs_no_repository_code() -> None:
    steps = _load(WORKFLOWS / "release.yml")["jobs"]["release"]["steps"]
    assert not any(str(step.get("uses", "")).startswith("actions/checkout@") for step in steps)


def test_release_is_a_draft_until_the_last_step() -> None:
    steps = _load(WORKFLOWS / "release.yml")["jobs"]["release"]["steps"]
    create = next(step["run"] for step in steps if "gh release create" in step.get("run", ""))
    for flag in ("--draft", "--verify-tag", "--prerelease"):
        assert flag in create
    assert steps[-1]["run"].strip() == 'gh release edit "$GITHUB_REF_NAME" --draft=false'
    publishing = [step for step in steps if "--draft=false" in step.get("run", "")]
    assert publishing == [steps[-1]]
