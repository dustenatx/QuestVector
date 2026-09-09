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

    Attributes:
        template_id: Filename stem, e.g. "devops-senior-mgr".
        title: Human-readable role title.
        categories: Weighted scoring categories.
        source_path: Filesystem path the template was loaded from, if any.
    """

    template_id: str
    title: str
    categories: tuple[TemplateCategory, ...] = field(default_factory=tuple)
    source_path: str | None = None

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
        red_flags: Keywords or conditions flagged as critical (Lock-On Red)
            — e.g. a category with zero coverage and a high template weight.
        alert_level: Overall severity derived from the score and red flags.
    """

    g_force_score: float
    category_scores: tuple[CategoryScore, ...] = field(default_factory=tuple)
    gaps: tuple[str, ...] = field(default_factory=tuple)
    red_flags: tuple[str, ...] = field(default_factory=tuple)
    alert_level: AlertLevel = AlertLevel.WARNING
