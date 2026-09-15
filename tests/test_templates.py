"""Unit tests for questvector.core.templates."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from questvector.core.templates import (
    find_template_file,
    list_template_files,
    load_template,
    template_id_from_filename,
    validate_template,
    validate_template_file,
    write_template,
)
from questvector.core.models import MissionTemplate, TemplateCategory
from questvector.exceptions import ValidationError

RECONCILED_SCHEMA_YAML = """
schema_version: "1.0"
mission_id: sr-cloud-architect
metadata:
  title: Senior Cloud Architect
  author: Jane Contributor
  version: "1.0.0"
  description: A test of the reconciled schema.
  tags: [cloud, architecture]

categories:
  - name: cloud
    weight: 0.7
    keywords: [aws, terraform]
  - name: leadership
    weight: 0.3
    keywords: [mentoring]

jd_analysis:
  gap_coverage_threshold: 0.5
  red_flag_phrases:
    - "unrealistic requirement"
    - "vague job scope"

output_formatting:
  target_page_budget: 2
  tone_style: executive-tactical
"""

VALID_YAML = """
id: test-template
title: Test Role
categories:
  - name: cloud
    weight: 0.6
    keywords: [aws, terraform]
  - name: leadership
    weight: 0.4
    keywords: [mentoring]
"""

INVALID_WEIGHT_YAML = """
id: test-template
title: Test Role
categories:
  - name: cloud
    weight: 0.3
    keywords: [aws]
  - name: leadership
    weight: 0.3
    keywords: [mentoring]
"""


def _write(tmp_path: Path, content: str, name: str = "template.yaml") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_load_template_valid_yaml(tmp_path: Path) -> None:
    path = _write(tmp_path, VALID_YAML)
    template = load_template(path)
    assert template.template_id == "test-template"
    assert len(template.categories) == 2
    assert template.categories[0].weight == 0.6


def test_load_template_defaults_id_and_title_to_filename_stem(tmp_path: Path) -> None:
    minimal = "categories:\n  - name: a\n    weight: 1.0\n"
    path = _write(tmp_path, minimal, name="my-role.yaml")
    template = load_template(path)
    assert template.template_id == "my-role"
    assert template.title == "my-role"


def test_load_template_malformed_yaml_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "id: [unclosed")
    with pytest.raises(ValidationError):
        load_template(path)


def test_load_template_non_mapping_root_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(ValidationError):
        load_template(path)


def test_load_template_missing_categories_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "id: x\ntitle: y\n")
    with pytest.raises(ValidationError):
        load_template(path)


def test_load_template_category_missing_weight_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "categories:\n  - name: a\n")
    with pytest.raises(ValidationError):
        load_template(path)


def test_load_template_category_non_numeric_weight_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "categories:\n  - name: a\n    weight: not-a-number\n")
    with pytest.raises(ValidationError):
        load_template(path)


def test_load_template_category_not_a_mapping_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "categories:\n  - just-a-string\n")
    with pytest.raises(ValidationError):
        load_template(path)


def test_load_template_category_keywords_not_a_list_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "categories:\n  - name: a\n    weight: 1.0\n    keywords: not-a-list\n")
    with pytest.raises(ValidationError):
        load_template(path)


def test_validate_template_within_tolerance_is_valid() -> None:
    template = MissionTemplate(
        "t", "T", (TemplateCategory("a", 0.5), TemplateCategory("b", 0.5))
    )
    _, result = validate_template(template)
    assert result.valid is True
    assert result.fixed is False


def test_validate_template_out_of_tolerance_without_fix_is_invalid() -> None:
    template = MissionTemplate(
        "t", "T", (TemplateCategory("a", 0.3), TemplateCategory("b", 0.3))
    )
    _, result = validate_template(template, fix=False)
    assert result.valid is False
    assert result.fixed is False


def test_validate_template_with_fix_rescales_to_one() -> None:
    template = MissionTemplate(
        "t", "T", (TemplateCategory("a", 0.3), TemplateCategory("b", 0.3))
    )
    fixed, result = validate_template(template, fix=True)
    assert result.valid is True
    assert result.fixed is True
    assert abs(fixed.weight_sum() - 1.0) < 0.005


def test_validate_template_fix_with_zero_weight_sum_raises() -> None:
    template = MissionTemplate("t", "T", (TemplateCategory("a", 0.0), TemplateCategory("b", 0.0)))
    with pytest.raises(ValidationError):
        validate_template(template, fix=True)


def test_write_template_round_trips(tmp_path: Path) -> None:
    template = MissionTemplate(
        "t", "Title", (TemplateCategory("a", 0.5, ("x", "y")), TemplateCategory("b", 0.5))
    )
    path = tmp_path / "out.yaml"
    write_template(template, path)

    reloaded = load_template(path)
    assert reloaded.template_id == "t"
    assert reloaded.categories[0].keywords == ("x", "y")


def test_validate_template_file_persists_fix(tmp_path: Path) -> None:
    path = _write(tmp_path, INVALID_WEIGHT_YAML)

    result = validate_template_file(path, fix=True)

    assert result.fixed is True
    on_disk = yaml.safe_load(path.read_text(encoding="utf-8"))
    total_weight = sum(c["weight"] for c in on_disk["categories"])
    assert abs(total_weight - 1.0) < 0.005


def test_validate_template_file_without_fix_leaves_file_unchanged(tmp_path: Path) -> None:
    path = _write(tmp_path, INVALID_WEIGHT_YAML)
    original = path.read_text(encoding="utf-8")

    result = validate_template_file(path, fix=False)

    assert result.valid is False
    assert path.read_text(encoding="utf-8") == original


# --- Reconciled schema (mission_id/metadata/jd_analysis/output_formatting) ---


def test_load_template_reconciled_schema_parses_all_sections(tmp_path: Path) -> None:
    path = _write(tmp_path, RECONCILED_SCHEMA_YAML, name="sr-cloud-architect.qv-mission.yaml")

    template = load_template(path)

    assert template.template_id == "sr-cloud-architect"
    assert template.title == "Senior Cloud Architect"
    assert template.author == "Jane Contributor"
    assert template.version == "1.0.0"
    assert template.description == "A test of the reconciled schema."
    assert template.tags == ("cloud", "architecture")
    assert template.red_flag_phrases == ("unrealistic requirement", "vague job scope")
    assert template.gap_coverage_threshold == 0.5
    assert template.tone_style == "executive-tactical"
    assert template.target_page_budget == 2


def test_load_template_legacy_flat_schema_still_works(tmp_path: Path) -> None:
    # Pre-reconciliation shape: top-level id/title, no metadata/jd_analysis/output_formatting.
    path = _write(tmp_path, VALID_YAML)

    template = load_template(path)

    assert template.template_id == "test-template"
    assert template.title == "Test Role"
    assert template.author is None
    assert template.red_flag_phrases == ()
    assert template.gap_coverage_threshold is None


def test_load_template_metadata_not_a_mapping_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "categories:\n  - name: a\n    weight: 1.0\nmetadata: not-a-mapping\n")
    with pytest.raises(ValidationError):
        load_template(path)


def test_load_template_jd_analysis_not_a_mapping_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "categories:\n  - name: a\n    weight: 1.0\njd_analysis: not-a-mapping\n")
    with pytest.raises(ValidationError):
        load_template(path)


def test_load_template_red_flag_phrases_not_a_list_raises(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "categories:\n  - name: a\n    weight: 1.0\njd_analysis:\n  red_flag_phrases: not-a-list\n",
    )
    with pytest.raises(ValidationError):
        load_template(path)


def test_load_template_gap_coverage_threshold_non_numeric_raises(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "categories:\n  - name: a\n    weight: 1.0\njd_analysis:\n  gap_coverage_threshold: not-a-number\n",
    )
    with pytest.raises(ValidationError):
        load_template(path)


def test_load_template_output_formatting_not_a_mapping_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "categories:\n  - name: a\n    weight: 1.0\noutput_formatting: not-a-mapping\n")
    with pytest.raises(ValidationError):
        load_template(path)


def test_load_template_target_page_budget_non_integer_raises(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "categories:\n  - name: a\n    weight: 1.0\noutput_formatting:\n  target_page_budget: not-a-number\n",
    )
    with pytest.raises(ValidationError):
        load_template(path)


def test_write_template_round_trips_reconciled_fields(tmp_path: Path) -> None:
    template = MissionTemplate(
        template_id="t",
        title="Title",
        categories=(TemplateCategory("a", 1.0, ("x",)),),
        author="Someone",
        version="2.0.0",
        description="Desc",
        tags=("a", "b"),
        red_flag_phrases=("bad phrase",),
        gap_coverage_threshold=0.6,
        tone_style="concise",
        target_page_budget=1,
    )
    path = tmp_path / "out.qv-mission.yaml"

    write_template(template, path)
    reloaded = load_template(path)

    assert reloaded.author == "Someone"
    assert reloaded.version == "2.0.0"
    assert reloaded.description == "Desc"
    assert reloaded.tags == ("a", "b")
    assert reloaded.red_flag_phrases == ("bad phrase",)
    assert reloaded.gap_coverage_threshold == 0.6
    assert reloaded.tone_style == "concise"
    assert reloaded.target_page_budget == 1

    on_disk = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert on_disk["mission_id"] == "t"
    assert on_disk["schema_version"] == "1.0"


# --- Template file discovery helpers ---


def test_template_id_from_filename_strips_compound_extension() -> None:
    assert template_id_from_filename("devops-senior-mgr.qv-mission.yaml") == "devops-senior-mgr"
    assert template_id_from_filename("devops-senior-mgr.qv-mission.yml") == "devops-senior-mgr"


def test_template_id_from_filename_strips_plain_extension() -> None:
    assert template_id_from_filename("legacy-template.yaml") == "legacy-template"


def test_find_template_file_searches_dirs_in_order(tmp_path: Path) -> None:
    starter = tmp_path / "starter"
    community = tmp_path / "community"
    starter.mkdir()
    community.mkdir()
    (starter / "role-a.qv-mission.yaml").write_text("categories:\n  - name: a\n    weight: 1.0\n", encoding="utf-8")
    (community / "role-b.qv-mission.yaml").write_text("categories:\n  - name: b\n    weight: 1.0\n", encoding="utf-8")

    found_a = find_template_file([starter, community], "role-a")
    found_b = find_template_file([starter, community], "role-b")
    found_missing = find_template_file([starter, community], "role-c")

    assert found_a == starter / "role-a.qv-mission.yaml"
    assert found_b == community / "role-b.qv-mission.yaml"
    assert found_missing is None


def test_list_template_files_deduplicates_by_id(tmp_path: Path) -> None:
    directory = tmp_path / "templates"
    directory.mkdir()
    # Same mission id, two on-disk conventions -- should count as one template.
    (directory / "role.qv-mission.yaml").write_text("categories: []\n", encoding="utf-8")
    (directory / "role.yaml").write_text("categories: []\n", encoding="utf-8")
    (directory / "other.yaml").write_text("categories: []\n", encoding="utf-8")
    (directory / "notes.txt").write_text("ignore me", encoding="utf-8")

    files = list_template_files(directory)

    assert len(files) == 2
    assert not any(f.name == "notes.txt" for f in files)


def test_list_template_files_on_missing_directory_returns_empty(tmp_path: Path) -> None:
    assert list_template_files(tmp_path / "does-not-exist") == []
