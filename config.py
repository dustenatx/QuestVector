"""Static configuration: theme tokens, filenames, and tunables.

Centralizing these values keeps the "Tactical Ops Flight Deck" brand spec
(see MASTER_DEVELOPER_SPEC.pdf, Section 1) out of business logic and out of
the UI layer's hardcoded strings, so either can change independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    """Color palette from the QuestVector Brand Bible (spec Section 1).

    Attributes:
        background: Canvas background color ("Obsidian Void").
        panel: Card/panel fill color ("Cockpit Slate").
        accent: Primary accent / gauge color ("Vector Cyan").
        success: Match-high / success color ("Tactical Green").
        warning: Gaps / warnings color ("Afterburner Amber").
        critical: Critical alert color ("Lock-On Red").
    """

    background: str = "#0b0f19"
    panel: str = "#0d1322"
    accent: str = "#00f2fe"
    success: str = "#10b981"
    warning: str = "#f59e0b"
    critical: str = "#ef4444"


THEME = ThemeTokens()

# Canonical dossier filenames a QuestVector workspace expects to find/create.
CAPABILITIES_FILENAME = "Capabilities.md"
CHRONOLOGY_FILENAME = "Chronology.md"
IMPACT_FILENAME = "Impact.md"

DOSSIER_FILENAMES: tuple[str, ...] = (
    CAPABILITIES_FILENAME,
    CHRONOLOGY_FILENAME,
    IMPACT_FILENAME,
)

# Workspace layout.
TEMPLATES_DIRNAME = "templates"
STARTER_TEMPLATES_DIRNAME = "starter"
BUNDLES_DIRNAME = "bundles"
LOCK_FILENAME = ".questvector.lock"
VAULT_FILENAME = ".questvector.vault"

# Mission template weight validation.
WEIGHT_SUM_TARGET = 1.00
WEIGHT_SUM_TOLERANCE = 0.005  # +/- tolerance before a template is flagged.

# Matching engine tunables (documented assumptions — see core/matcher.py).
STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
        "have", "he", "in", "is", "it", "its", "of", "on", "or", "that",
        "the", "to", "was", "were", "will", "with", "you", "your", "we",
        "our", "their", "this", "these", "those", "but", "not", "can",
        "will", "should", "would", "may", "must", "into", "than", "such",
        "etc", "including", "including", "years", "year", "experience",
        "experienced", "strong", "excellent", "ability", "abilities",
    }
)

DEFAULT_CONFIG_DIR = Path.home() / ".questvector"

# Matching engine thresholds (documented assumptions — see core/matcher.py).
# A category is flagged as a critical red flag (Lock-On Red) when its
# template weight is at least this high AND its dossier coverage is zero —
# i.e. a heavily-weighted requirement the dossier says nothing about at all.
MATCH_RED_FLAG_WEIGHT_THRESHOLD = 0.20

# Overall G-Force score bands used to derive AlertLevel when no red flag
# fired on its own.
MATCH_CRITICAL_SCORE = 40.0
MATCH_WARNING_SCORE = 70.0
