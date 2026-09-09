"""Shared pytest fixtures for the QuestVector test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from questvector.core import workspace


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
