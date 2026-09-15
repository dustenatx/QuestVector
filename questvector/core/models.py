"""Core domain models shared across the parser, matcher, templates, and
exporter modules.

All models are immutable, slotted dataclasses: instances are produced once
by a parser/loader and then read by downstream consumers, so there is no
need for mutability and the immutability makes them safe to share across the
CLI, the desktop JS bridge, and background threads without copying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AlertLevel(str, Enum):
    """Severity levels mapped to the Brand Bible's HUD alert colors.

    Values match spec Section 1: ``SUCCESS`` -> Tactical Green,
    ``WARNING`` -> Afterburner Amber, ``CRITICAL`` -> Lock-On Red.
    """

    SUCCESS = "success"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class Capability:
    """A single capability/skill entry parsed from ``Capabilities.md``.

    Attributes:
        domain: The capability domain heading it was parsed under
            (e.g. "Platform Engineering").
        text: The capability statement itself, verbatim from the bullet.
        keywords: Lowercased, stopword-filtered tokens extracted from
            ``text`` for use by the matching engine.
    """

    domain: str
    text: str
    keywords: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ChronologyEntry:
    """A single role/timeframe entry parsed from ``Chronology.md``.

    Attributes:
        heading: The raw heading line (e.g. "Acme Corp — Senior SRE
            (2020–2023)").
        bullets: Responsibility/achievement bullet lines under the heading.
        keywords: Lowercased, stopword-filtered tokens extracted from all
            bullets, for use by the matching engine.
    """

    heading: str
    bullets: tuple[str, ...] = field(default_factory=tuple)
    keywords: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ImpactStatement:
    """A single quantified-impact entry parsed from ``Impact.md``.

    Attributes:
        heading: The raw heading line the statement was grouped under.
        bullets: Impact statement bullet lines under the heading.
        keywords: Lowercased, stopword-filtered tokens extracted from all
            bullets, for use by the matching engine.
    """

    heading: str
    bullets: tuple[str, ...] = field(default_factory=tuple)
    keywords: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class Dossier:
    """The full parsed dossier: capabilities, chronology, and impact.

    Attributes:
        capabilities: All parsed capability entries.
        chronology: All parsed chronology entries.
        impact: All parsed impact statement entries.
    """

    capabilities: tuple[Capability, ...] = field(default_factory=tuple)
    chronology: tuple[ChronologyEntry, ...] = field(default_factory=tuple)
    impact: tuple[ImpactStatement, ...] = field(default_factory=tuple)

    def all_keywords(self) -> frozenset[str]:
        """Return the union of every keyword across the whole dossier.

        Returns:
            A frozenset of lowercased keyword tokens drawn from
            capabilities, chronology, and impact sections combined.
        """
        keywords: set[str] = set()
        for cap in self.capabilities:
            keywords |= cap.keywords
        for entry in self.chronology:
            keywords |= entry.keywords
        for stmt in self.impact:
            keywords |= stmt.keywords
        return frozenset(keywords)


@dataclass(frozen=True, slots=True)
class JobDescription:
    """A parsed/normalized job description used as the matcher's target.

    Attributes:
        source: Human-readable origin of the text (e.g. a file path or
            "clipboard").
        raw_text: The original, unmodified JD text.
        keywords: Lowercased, stopword-filtered tokens extracted from
            ``raw_text``.
    """

    source: str
    raw_text: str
    keywords: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class TemplateCategory:
    """A single scoring category within a mission template.

    Attributes:
        name: Category label (e.g. "cloud_infrastructure").
        weight: Fractional weight in ``[0.0, 1.0]``; all categories in a
            template should sum to ``config.WEIGHT_SUM_TARGET``.
        keywords: Keywords associated with this category, matched against
            both the dossier and the job description.
    """

    name: str
    weight: float
    keywords: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MissionTemplate:
    """A community/starter mission template (spec Section 4).

    Schema reconciled between MASTER_DEVELOPER_SPEC.pdf Section 4 (which
    names the templates but not their format) and the community
    ``CONTRIBUTING_TEMPLATES.md`` schema (``mission_id``/``metadata``/
    ``jd_analysis``/``output_formatting``) already published on the
    project's GitHub repo — see :mod:`questvector.core.templates` for the
    full reconciliation notes. ``categories`` (this build's own weighted
    JD-matching dimensions) is kept from the original Stage 1 design rather
    than the community doc's fixed ``narrative_weighting`` three-way split,
    since per-role category keywords are strictly more expressive and this
    is what :mod:`questvector.core.matcher` is built and tested against.

    Attributes:
        template_id: Mission identifier (``mission_id`` in YAML; filename
            stem if omitted).
        title: Human-readable role title.
        categories: Weighted JD-matching scoring categories.
        source_path: Filesystem path the template was loaded from, if any.
        author: Optional contributor attribution.
        version: Optional template version string.
        description: Optional human-readable summary.
        tags: Optional free-form category tags.
        red_flag_phrases: Literal phrases to scan for directly in a job
            description's text (e.g. "unrealistic requirement") — distinct
            from the matcher's own derived, coverage-based red flags.
        gap_coverage_threshold: Category coverage fraction below which a
            whole category is additionally reported as "weak" (see
            :class:`MatchResult.weak_categories`), independent of
            individual missing keywords.
        tone_style: Optional narrative-generation tone hint (e.g.
            "executive-tactical"), passed through to
            :func:`questvector.core.llm.build_narrative_prompt` when set.
        target_page_budget: Optional target page count for exported
            bundles. Captured and validated, but not yet enforced by
            :mod:`questvector.core.exporter` — documented as a known gap
            rather than silently ignored.
    """

    template_id: str
    title: str
    categories: tuple[TemplateCategory, ...] = field(default_factory=tuple)
    source_path: str | None = None
    author: str | None = None
    version: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    red_flag_phrases: tuple[str, ...] = field(default_factory=tuple)
    gap_coverage_threshold: float | None = None
    tone_style: str | None = None
    target_page_budget: int | None = None

    def weight_sum(self) -> float:
        """Return the sum of all category weights.

        Returns:
            The arithmetic sum of ``weight`` across ``categories``.
        """
        return sum(category.weight for category in self.categories)


@dataclass(frozen=True, slots=True)
class CategoryScore:
    """Per-category result from a match run.

    Attributes:
        name: Category name (matches :class:`TemplateCategory.name`).
        weight: The category's weight as used in this match.
        coverage: Fraction ``[0.0, 1.0]`` of the category's keywords found
            in both the dossier and the job description.
        matched_keywords: Keywords present in the JD and satisfied by the
            dossier.
        gap_keywords: Keywords present in the JD but absent from the
            dossier for this category.
    """

    name: str
    weight: float
    coverage: float
    matched_keywords: tuple[str, ...] = field(default_factory=tuple)
    gap_keywords: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Result of running the Micro-Diff Matching Engine (spec Section 2/3).

    Attributes:
        g_force_score: Overall weighted match percentage, ``0.0``-``100.0``.
        category_scores: Per-category breakdown.
        gaps: Keywords flagged as missing/weak (Afterburner Amber).
        red_flags: Conditions flagged as critical (Lock-On Red) — a
            category with zero coverage and a high template weight, or a
            template-declared ``red_flag_phrases`` entry found verbatim in
            the job description text.
        weak_categories: Category names whose coverage fell below the
            template's ``gap_coverage_threshold`` (when set), reported
            separately from per-keyword ``gaps`` since a category can be
            "weak" overall without every individual keyword being missing.
        alert_level: Overall severity derived from the score and red flags.
    """

    g_force_score: float
    category_scores: tuple[CategoryScore, ...] = field(default_factory=tuple)
    gaps: tuple[str, ...] = field(default_factory=tuple)
    red_flags: tuple[str, ...] = field(default_factory=tuple)
    weak_categories: tuple[str, ...] = field(default_factory=tuple)
    alert_level: AlertLevel = AlertLevel.WARNING
