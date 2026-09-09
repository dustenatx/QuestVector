"""Unit tests for questvector.core.templates."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from questvector.core.templates import (
    load_template,
    validate_template,
    validate_template_file,
    write_template,
)
from questvector.core.models import MissionTemplate, TemplateCategory
from questvector.exceptions import ValidationError

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
