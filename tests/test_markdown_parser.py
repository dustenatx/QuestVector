"""Unit tests for questvector.core.markdown_parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from questvector.core.markdown_parser import (
    parse_capabilities,
    parse_chronology,
    parse_dossier,
    parse_impact,
    tokenize,
)
from questvector.exceptions import ParseError


def test_tokenize_lowercases_and_strips_stopwords() -> None:
    tokens = tokenize("The Senior AWS Engineer is a great fit for the team")
    assert "the" not in tokens
    assert "is" not in tokens
    assert "a" not in tokens
    assert "aws" in tokens
    assert "engineer" in tokens
    assert "senior" in tokens


def test_tokenize_empty_string_returns_empty_set() -> None:
    assert tokenize("") == frozenset()


def test_parse_capabilities_groups_bullets_under_domain(tmp_path: Path, sample_capabilities_md: str) -> None:
    path = tmp_path / "Capabilities.md"
    path.write_text(sample_capabilities_md, encoding="utf-8")

    capabilities = parse_capabilities(path)

    assert len(capabilities) == 4
    assert capabilities[0].domain == "Cloud Infrastructure"
    assert "aws" in capabilities[0].keywords
    assert capabilities[2].domain == "Leadership"


def test_parse_capabilities_missing_file_raises_parse_error(tmp_path: Path) -> None:
    with pytest.raises(ParseError):
        parse_capabilities(tmp_path / "does-not-exist.md")


def test_parse_capabilities_empty_file_raises_parse_error(tmp_path: Path) -> None:
    path = tmp_path / "Capabilities.md"
    path.write_text("   \n\n  ", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_capabilities(path)


def test_parse_capabilities_no_headings_or_bullets_raises_parse_error(tmp_path: Path) -> None:
    path = tmp_path / "Capabilities.md"
    path.write_text("Just some prose with no structure at all.", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_capabilities(path)


def test_parse_capabilities_bad_encoding_raises_parse_error(tmp_path: Path) -> None:
    path = tmp_path / "Capabilities.md"
    path.write_bytes(b"## Domain\n- \xff\xfe invalid utf-8 bytes\n")
    with pytest.raises(ParseError):
        parse_capabilities(path)


def test_parse_capabilities_orphan_bullets_before_heading_are_uncategorized(tmp_path: Path) -> None:
    path = tmp_path / "Capabilities.md"
    path.write_text("- an orphan bullet\n\n## Real Domain\n- a real bullet\n", encoding="utf-8")

    capabilities = parse_capabilities(path)

    assert capabilities[0].domain == "Uncategorized"
    assert capabilities[1].domain == "Real Domain"


def test_parse_chronology_groups_bullets_by_role(tmp_path: Path, sample_chronology_md: str) -> None:
    path = tmp_path / "Chronology.md"
    path.write_text(sample_chronology_md, encoding="utf-8")

    entries = parse_chronology(path)

    assert len(entries) == 1
    assert entries[0].heading == "Acme Corp — Senior SRE (2020-2023)"
    assert len(entries[0].bullets) == 2
    assert "aws" in entries[0].keywords


def test_parse_impact_groups_bullets_by_heading(tmp_path: Path, sample_impact_md: str) -> None:
    path = tmp_path / "Impact.md"
    path.write_text(sample_impact_md, encoding="utf-8")

    statements = parse_impact(path)

    assert len(statements) == 1
    assert statements[0].heading == "Cost Optimization"


def test_parse_dossier_tolerates_missing_files(tmp_path: Path, sample_capabilities_md: str) -> None:
    (tmp_path / "Capabilities.md").write_text(sample_capabilities_md, encoding="utf-8")
    # Chronology.md and Impact.md intentionally absent.

    dossier = parse_dossier(tmp_path)

    assert len(dossier.capabilities) == 4
    assert dossier.chronology == ()
    assert dossier.impact == ()


def test_parse_dossier_raises_if_present_file_is_malformed(tmp_path: Path, sample_capabilities_md: str) -> None:
    (tmp_path / "Capabilities.md").write_text(sample_capabilities_md, encoding="utf-8")
    (tmp_path / "Chronology.md").write_text("", encoding="utf-8")

    with pytest.raises(ParseError):
        parse_dossier(tmp_path)
