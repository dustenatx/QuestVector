"""Mission template loading, YAML schema validation, and weight auto-fix.

Spec reference: MASTER_DEVELOPER_SPEC.pdf Section 2 lists a "YAML Schema
Validator" and Section 3 defines ``qv template validate <path> [--fix]
[--json]`` as "Lints community mission YAML files, auto-adjusts weightings
to 1.00." The spec itself never publishes the YAML schema, and this
project's ``CONTRIBUTING_TEMPLATES.md`` (also AI-authored, independently of
this build) publishes a *different* one. This module's schema reconciles
the two rather than picking one over the other::

    schema_version: "1.0"
    mission_id: devops-senior-mgr        # optional; defaults to the filename stem
    metadata:
      title: Senior DevOps Manager       # optional; defaults to mission_id
      author: Jane Contributor           # optional
      version: "1.0.0"                   # optional
      description: A short summary.      # optional
      tags: [devops, platform]           # optional

    categories:                          # kept from this build's original design --
      - name: cloud_infrastructure       # per-role weighted JD-matching dimensions,
        weight: 0.35                     # more expressive than CONTRIBUTING_TEMPLATES.md's
        keywords: [aws, terraform]       # fixed capabilities/chronology/impact_stories split
      - name: leadership
        weight: 0.25
        keywords: [mentoring, budget]
      # ... weights across all categories should sum to 1.00

    jd_analysis:                          # from CONTRIBUTING_TEMPLATES.md, kept
      gap_coverage_threshold: 0.5         # optional
      red_flag_phrases: [unrealistic requirement, vague job scope]  # optional

    output_formatting:                    # from CONTRIBUTING_TEMPLATES.md, kept
      target_page_budget: 2               # optional
      tone_style: executive-tactical      # optional

Only ``name`` and ``weight`` are required per category; ``keywords`` may be
omitted (the matching engine then falls back to scoring that category
against the full job-description keyword set — see
:mod:`questvector.core.matcher`). Every other top-level section is
optional. For backward compatibility with templates written against this
build's original (pre-reconciliation) schema, a flat ``id``/``title`` at
the document root is still accepted when ``mission_id``/``metadata`` are
absent.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from questvector.config import WEIGHT_SUM_TARGET, WEIGHT_SUM_TOLERANCE
from questvector.core.models import MissionTemplate, TemplateCategory
from questvector.exceptions import ValidationError

#: Supported template file extensions, longest/most-specific first.
#: ``.qv-mission.yaml``/``.yml`` is the community-repo convention
#: documented in ``CONTRIBUTING_TEMPLATES.md``; plain ``.yaml``/``.yml`` is
#: accepted for backward compatibility with this build's original files.
TEMPLATE_EXTENSIONS: tuple[str, ...] = (".qv-mission.yaml", ".qv-mission.yml", ".yaml", ".yml")


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


def _string_list(raw: Any, *, field_name: str, template_id: str) -> tuple[str, ...]:
    """Validate and coerce an optional list-of-strings field.

    Args:
        raw: The raw value (expected to be a list, or absent/``None``).
        field_name: Field name, used only for error context.
        template_id: The owning template's id, used only for error context.

    Returns:
        A tuple of strings, or an empty tuple if ``raw`` is ``None``.

    Raises:
        ValidationError: If ``raw`` is present but not a list.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValidationError(
            f"Mission template field '{field_name}' must be a list",
            context={"template_id": template_id},
        )
    return tuple(str(item) for item in raw)


def load_template(path: Path) -> MissionTemplate:
    """Load and structurally validate a mission template YAML file.

    Args:
        path: Path to the ``.qv-mission.yaml`` (or legacy ``.yaml``/``.yml``)
            mission template file.

    Returns:
        A validated :class:`MissionTemplate` (structure only — weight-sum
        validation is a separate step; see :func:`validate_template`).

    Raises:
        ValidationError: If the file cannot be read, is not valid YAML, is
            not a mapping at the root, has no ``categories`` list, or any
            section fails validation.
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

    template_id = str(data.get("mission_id", data.get("id", path.stem)))

    metadata = data.get("metadata") or {}
    if metadata and not isinstance(metadata, dict):
        raise ValidationError(
            f"Mission template 'metadata' must be a mapping: {path.name}",
            context={"path": str(path)},
        )
    # Legacy flat shape: a top-level 'title' is accepted when 'metadata' is absent.
    title = str(metadata.get("title", data.get("title", template_id)))
    author = metadata.get("author")
    version = metadata.get("version")
    description = metadata.get("description")
    tags = _string_list(metadata.get("tags"), field_name="metadata.tags", template_id=template_id)

    categories_raw = data.get("categories")
    if not isinstance(categories_raw, list) or not categories_raw:
        raise ValidationError(
            f"Mission template has no non-empty 'categories' list: {path.name}",
            context={"path": str(path)},
        )
    categories = tuple(
        _coerce_category(category, template_id=template_id) for category in categories_raw
    )

    jd_analysis = data.get("jd_analysis") or {}
    if jd_analysis and not isinstance(jd_analysis, dict):
        raise ValidationError(
            f"Mission template 'jd_analysis' must be a mapping: {path.name}",
            context={"path": str(path)},
        )
    red_flag_phrases = _string_list(
        jd_analysis.get("red_flag_phrases"), field_name="jd_analysis.red_flag_phrases", template_id=template_id
    )
    gap_coverage_threshold_raw = jd_analysis.get("gap_coverage_threshold")
    try:
        gap_coverage_threshold = (
            float(gap_coverage_threshold_raw) if gap_coverage_threshold_raw is not None else None
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "Mission template 'jd_analysis.gap_coverage_threshold' must be numeric",
            context={"template_id": template_id},
        ) from exc

    output_formatting = data.get("output_formatting") or {}
    if output_formatting and not isinstance(output_formatting, dict):
        raise ValidationError(
            f"Mission template 'output_formatting' must be a mapping: {path.name}",
            context={"path": str(path)},
        )
    tone_style = output_formatting.get("tone_style")
    target_page_budget_raw = output_formatting.get("target_page_budget")
    try:
        target_page_budget = int(target_page_budget_raw) if target_page_budget_raw is not None else None
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "Mission template 'output_formatting.target_page_budget' must be an integer",
            context={"template_id": template_id},
        ) from exc

    return MissionTemplate(
        template_id=template_id,
        title=title,
        categories=categories,
        source_path=str(path),
        author=str(author) if author is not None else None,
        version=str(version) if version is not None else None,
        description=str(description) if description is not None else None,
        tags=tags,
        red_flag_phrases=red_flag_phrases,
        gap_coverage_threshold=gap_coverage_threshold,
        tone_style=str(tone_style) if tone_style is not None else None,
        target_page_budget=target_page_budget,
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
        author=template.author,
        version=template.version,
        description=template.description,
        tags=template.tags,
        red_flag_phrases=template.red_flag_phrases,
        gap_coverage_threshold=template.gap_coverage_threshold,
        tone_style=template.tone_style,
        target_page_budget=template.target_page_budget,
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
    metadata: dict[str, Any] = {"title": template.title}
    if template.author is not None:
        metadata["author"] = template.author
    if template.version is not None:
        metadata["version"] = template.version
    if template.description is not None:
        metadata["description"] = template.description
    if template.tags:
        metadata["tags"] = list(template.tags)

    data: dict[str, Any] = {
        "schema_version": "1.0",
        "mission_id": template.template_id,
        "metadata": metadata,
        "categories": [
            {"name": c.name, "weight": c.weight, "keywords": list(c.keywords)}
            for c in template.categories
        ],
    }

    jd_analysis: dict[str, Any] = {}
    if template.gap_coverage_threshold is not None:
        jd_analysis["gap_coverage_threshold"] = template.gap_coverage_threshold
    if template.red_flag_phrases:
        jd_analysis["red_flag_phrases"] = list(template.red_flag_phrases)
    if jd_analysis:
        data["jd_analysis"] = jd_analysis

    output_formatting: dict[str, Any] = {}
    if template.target_page_budget is not None:
        output_formatting["target_page_budget"] = template.target_page_budget
    if template.tone_style is not None:
        output_formatting["tone_style"] = template.tone_style
    if output_formatting:
        data["output_formatting"] = output_formatting

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


def template_id_from_filename(filename: str) -> str:
    """Derive a template id from a filename, stripping known extensions.

    Handles the compound ``.qv-mission.yaml``/``.yml`` extension correctly
    (unlike :attr:`pathlib.Path.stem`, which would only strip ``.yaml``
    and leave a trailing ``.qv-mission``).

    Args:
        filename: A template file's base name (not a full path).

    Returns:
        The filename with its template extension removed.
    """
    for extension in TEMPLATE_EXTENSIONS:
        if filename.endswith(extension):
            return filename[: -len(extension)]
    return Path(filename).stem


def find_template_file(search_dirs: Iterable[Path], template_id: str) -> Path | None:
    """Search a list of directories, in order, for a template matching an id.

    Args:
        search_dirs: Directories to search, in priority order (e.g.
            ``templates/starter`` before ``templates/community``).
        template_id: The mission id to look for.

    Returns:
        The first matching file path found, or ``None`` if no directory
        contains a file named ``<template_id>`` with a supported extension.
    """
    for directory in search_dirs:
        for extension in TEMPLATE_EXTENSIONS:
            candidate = directory / f"{template_id}{extension}"
            if candidate.exists():
                return candidate
    return None


def list_template_files(directory: Path) -> list[Path]:
    """List all template files in a directory, one per distinct mission id.

    Args:
        directory: The directory to scan (non-recursive).

    Returns:
        A sorted list of template file paths. If a directory contains both
        ``<id>.qv-mission.yaml`` and a legacy ``<id>.yaml`` for the same id,
        only one is returned (whichever sorts first), since they represent
        the same mission id.
    """
    if not directory.is_dir():
        return []
    by_id: dict[str, Path] = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file() or not (path.name.endswith(".yaml") or path.name.endswith(".yml")):
            continue
        by_id.setdefault(template_id_from_filename(path.name), path)
    return sorted(by_id.values())
