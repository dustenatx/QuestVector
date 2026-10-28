"""Shared pytest fixtures for the QuestVector test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from questvector.core import vault, workspace

# Iteration count used while testing, so each vault save or load takes about
# a millisecond instead of 150 ms. The shipped settings in vault.py are
# unchanged; tests marked ``real_kdf`` run against them.
FAST_KDF_ITERATIONS = 1_000


@pytest.fixture(autouse=True)
def fast_kdf(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lower the vault's PBKDF2 iteration count for every test not marked ``real_kdf``.

    Patches the write setting and the read floor together, so a vault saved
    during a test also loads. The format 1 setting (390,000) is left alone,
    so the v1 fixtures are read exactly as 1.1.0 wrote them.

    Args:
        request: The requesting test, checked for the ``real_kdf`` marker.
        monkeypatch: Restores the real values after the test.
    """
    if request.node.get_closest_marker("real_kdf"):
        return
    monkeypatch.setattr(vault, "_KDF_ITERATIONS", FAST_KDF_ITERATIONS)
    monkeypatch.setattr(vault, "_MIN_KDF_ITERATIONS", FAST_KDF_ITERATIONS)


@pytest.fixture()
def tmp_workspace(tmp_path: Path) -> Path:
    """A freshly-initialized QuestVector workspace under a temp directory.

    Args:
        tmp_path: pytest's built-in temp directory fixture.

    Returns:
        The initialized workspace directory path.
    """
    workspace_dir = tmp_path / "career-workspace"
    workspace.init_workspace(workspace_dir)
    return workspace_dir


@pytest.fixture()
def sample_capabilities_md() -> str:
    """Return sample ``Capabilities.md`` content for parser tests."""
    return (
        "## Cloud Infrastructure\n"
        "- Deep AWS experience including EC2, RDS, and cost optimization\n"
        "- Terraform and Kubernetes for infrastructure as code\n"
        "\n"
        "## Leadership\n"
        "- Managed global teams up to 60 engineers\n"
        "- Owned a $3M annual operating budget\n"
    )


@pytest.fixture()
def sample_chronology_md() -> str:
    """Return sample ``Chronology.md`` content for parser tests."""
    return (
        "## Acme Corp — Senior SRE (2020-2023)\n"
        "- Reduced AWS spend by 74% through rightsizing\n"
        "- On-call rotation lead for 15 engineers\n"
    )


@pytest.fixture()
def sample_impact_md() -> str:
    """Return sample ``Impact.md`` content for parser tests."""
    return (
        "## Cost Optimization\n"
        "- Cut monthly AWS cost from $27K to $7K\n"
    )


@pytest.fixture()
def sample_job_description() -> str:
    """Return a sample job description used across matcher tests."""
    return (
        "We are looking for a Senior DevOps Manager with deep AWS and "
        "Kubernetes experience, strong CI/CD automation background, and "
        "proven leadership managing engineering teams and budgets."
    )
