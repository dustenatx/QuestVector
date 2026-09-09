"""Mission template loading, YAML schema validation, and weight auto-fix.

Spec reference: MASTER_DEVELOPER_SPEC.pdf Section 2 lists a "YAML Schema
Validator" and Section 3 defines ``qv template validate <path> [--fix]
[--json]`` as "Lints community mission YAML files, auto-adjusts weightings
to 1.00." The spec never publishes the YAML schema itself, so — per the
Stage 1 blueprint — this module documents the schema this implementation
defines and validates against::

    id: devops-senior-mgr          # optional; defaults to the filename stem
    title: Senior DevOps Manager   # optional; defaults to id
    categories:
      - name: cloud_infrastructure
        weight: 0.35
        keywords: [aws, terraform, kubernetes]
      - name: leadership
        weight: 0.25
        keywords: [mentoring, budget, hiring]
      # ... weights across all categories should sum to 1.00

Only ``name`` and ``weight`` are required per category; ``keywords`` may be
omitted (the matching engine then falls back to scoring that category
against the full job-description keyword set — see
:mod:`questvector.core.matcher`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from questvector.config import WEIGHT_SUM_TARGET, WEIGHT_SUM_TOLERANCE
from questvector.core.models import MissionTemplate, TemplateCategory
from questvector.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class TemplateValidationResult:
    """Outcome of validating (and optionally fixing) a mission template.

    Attributes:
        template_id: The template's identifier.
        valid: Whether the template's weights are within tolerance of 1.00
            *after* any fix was applied (or as-is, if no fix was requested).
        weight_sum: The resulting weight sum.
        fixed: Whether an auto-fix rescale was actually applied.
        issues: Human-readable descriptions of what was found/changed.
    """

    template_id: str
    valid: bool
    weight_sum: float
    fixed: bool
    issues: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict for ``qv template validate --json``.

        Returns:
            A plain ``dict`` safe to pass to ``json.dumps``.
        """
        return {
            "template_id": self.template_id,
            "valid": self.valid,
            "weight_sum": self.weight_sum,
            "fixed": self.fixed,
            "issues": list(self.issues),
        }


def _coerce_category(raw: Any, *, template_id: str) -> TemplateCategory:
    """Validate and build one :class:`TemplateCategory` from raw YAML data.

    Args:
        raw: The raw mapping parsed for a single category entry.
        template_id: The owning template's id, used only for error context.

    Returns:
        A validated :class:`TemplateCategory`.

    Raises:
        ValidationError: If ``raw`` is not a mapping, is missing a required
            field, or has a field of the wrong type.
    """
    if not isinstance(raw, dict):
        raise ValidationError(
            "Mission template category must be a mapping",
            context={"template_id": template_id, "category": raw},
        )
    try:
        name = str(raw["name"])
        weight = float(raw["weight"])
    except KeyError as exc:
        raise ValidationError(
            f"Mission template category missing required field: {exc.args[0]}",
            context={"template_id": template_id, "category": raw},
        ) from exc
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "Mission template category 'weight' must be numeric",
            context={"template_id": template_id, "category": raw},
        ) from exc

    keywords_raw = raw.get("keywords", [])
    if not isinstance(keywords_raw, list):
        raise ValidationError(
            "Mission template category 'keywords' must be a list",
            context={"template_id": template_id, "category": name},
        )
    keywords = tuple(str(keyword).lower() for keyword in keywords_raw)
    return TemplateCategory(name=name, weight=weight, keywords=keywords)


def load_template(path: Path) -> MissionTemplate:
    """Load and structurally validate a mission template YAML file.

    Args:
        path: Path to the ``.yaml``/``.yml`` mission template file.

    Returns:
        A validated :class:`MissionTemplate` (structure only — weight-sum
        validation is a separate step; see :func:`validate_template`).

    Raises:
        ValidationError: If the file cannot be read, is not valid YAML, is
            not a mapping at the root, has no ``categories`` list, or any
            category fails :func:`_coerce_category`.
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(
            f"Could not read mission template: {path.name}", context={"path": str(path)}
        ) from exc

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ValidationError(
            f"Invalid YAML syntax in mission template: {path.name}",
            context={"path": str(path), "yaml_error": str(exc)},
        ) from exc

    if not isinstance(data, dict):
        raise ValidationError(
            f"Mission template root must be a YAML mapping: {path.name}",
            context={"path": str(path)},
        )

    template_id = str(data.get("id", path.stem))
    title = str(data.get("title", template_id))
    categories_raw = data.get("categories")
    if not isinstance(categories_raw, list) or not categories_raw:
        raise ValidationError(
            f"Mission template has no non-empty 'categories' list: {path.name}",
            context={"path": str(path)},
        )

    categories = tuple(
        _coerce_category(category, template_id=template_id) for category in categories_raw
    )
    return MissionTemplate(
        template_id=template_id, title=title, categories=categories, source_path=str(path)
    )


def validate_template(
    template: MissionTemplate, *, fix: bool = False
) -> tuple[MissionTemplate, TemplateValidationResult]:
    """Validate a template's category weights and optionally auto-fix them.

    Args:
        template: The template to validate.
        fix: If ``True`` and the weights are out of tolerance, rescale every
            category's weight proportionally so they sum to
            :data:`questvector.config.WEIGHT_SUM_TARGET`.

    Returns:
        A tuple of ``(template, result)`` — ``template`` is the original
        template unless ``fix`` produced a rescaled copy, in which case it
        is the rescaled copy.

    Raises:
        ValidationError: If ``fix`` is requested but the weights sum to zero
            or less (a proportional rescale is mathematically undefined).
    """
    weight_sum = template.weight_sum()
    within_tolerance = abs(weight_sum - WEIGHT_SUM_TARGET) <= WEIGHT_SUM_TOLERANCE

    if within_tolerance:
        return template, TemplateValidationResult(
            template_id=template.template_id, valid=True, weight_sum=weight_sum, fixed=False
        )

    issues = [
        f"Category weights sum to {weight_sum:.4f}, expected "
        f"{WEIGHT_SUM_TARGET:.2f} (+/-{WEIGHT_SUM_TOLERANCE})"
    ]

    if not fix:
        return template, TemplateValidationResult(
            template_id=template.template_id,
            valid=False,
            weight_sum=weight_sum,
            fixed=False,
            issues=tuple(issues),
        )

    if weight_sum <= 0:
        raise ValidationError(
            "Cannot auto-fix template: category weights sum to zero or less",
            context={"template_id": template.template_id, "weight_sum": weight_sum},
        )

    scale = WEIGHT_SUM_TARGET / weight_sum
    fixed_categories = tuple(
        TemplateCategory(name=c.name, weight=round(c.weight * scale, 4), keywords=c.keywords)
        for c in template.categories
    )
    fixed_template = MissionTemplate(
        template_id=template.template_id,
        title=template.title,
        categories=fixed_categories,
        source_path=template.source_path,
    )
    issues.append(f"Rescaled all category weights by factor {scale:.4f} to sum to {WEIGHT_SUM_TARGET:.2f}")
    return fixed_template, TemplateValidationResult(
        template_id=fixed_template.template_id,
        valid=True,
        weight_sum=fixed_template.weight_sum(),
        fixed=True,
        issues=tuple(issues),
    )


def write_template(template: MissionTemplate, path: Path) -> None:
    """Serialize a :class:`MissionTemplate` back to a YAML file.

    Args:
        template: The template to write (typically the rescaled result of
            :func:`validate_template` with ``fix=True``).
        path: Destination file path; overwritten if it already exists.

    Raises:
        ValidationError: If the file cannot be written.
    """
    data: dict[str, Any] = {
        "id": template.template_id,
        "title": template.title,
        "categories": [
            {"name": c.name, "weight": c.weight, "keywords": list(c.keywords)}
            for c in template.categories
        ],
    }
    try:
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    except OSError as exc:
        raise ValidationError(
            f"Could not write mission template: {path.name}", context={"path": str(path)}
        ) from exc


def validate_template_file(path: Path, *, fix: bool = False) -> TemplateValidationResult:
    """Load, validate, and (if requested and needed) fix a template file on disk.

    This is the single entry point ``qv template validate`` calls: it loads
    the file, validates weight sums, and — when ``fix=True`` and a fix was
    actually applied — writes the corrected template back to ``path``.

    Args:
        path: Path to the mission template YAML file.
        fix: Whether to auto-fix and persist out-of-tolerance weights.

    Returns:
        The :class:`TemplateValidationResult` describing the outcome.

    Raises:
        ValidationError: Propagated from :func:`load_template`,
            :func:`validate_template`, or :func:`write_template`.
    """
    template = load_template(path)
    fixed_template, result = validate_template(template, fix=fix)
    if result.fixed:
        write_template(fixed_template, path)
    return result
