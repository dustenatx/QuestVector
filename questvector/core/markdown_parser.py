"""Markdown AST parser for the QuestVector dossier documents.

Spec reference: MASTER_DEVELOPER_SPEC.pdf Section 2 describes a Rust-compiled
Wasm "Markdown AST Parser." The spec does not define QuestVector's own
Markdown dialect, so this module documents the schema this implementation
assumes (a deliberate design decision made per the Stage 1 blueprint, since
this build targets a generic/standalone schema rather than any specific
existing document format):

    ## <Heading text>
    - <bullet line>
    - <bullet line>

    ## <Next heading>
    - ...

Rules:
    * A level-2 heading (``## ...``) starts a new section. Its exact meaning
      (a capability *domain*, a chronology *role*, or an impact *grouping*)
      depends on which file it came from.
    * Bullet lines start with ``-``, ``*``, or ``•`` (optionally indented).
    * Blank lines and any other heading level are ignored/skipped rather
      than treated as errors, so lightly-decorated Markdown still parses.
    * Bullets appearing before any heading are grouped under the sentinel
      heading ``"Uncategorized"`` rather than rejected, since a missing
      leading heading is a common, easily-tolerated authoring slip.
    * A file that is empty, whitespace-only, or not valid UTF-8 text is
      treated as malformed and raises :class:`~questvector.exceptions.ParseError`.

Only the Standard Library (``re``, ``pathlib``) is used, per the project's
"stdlib before third-party" standard — no markdown parsing library is pulled
in for what is, in QuestVector's case, a deliberately small and regular
subset of Markdown.
"""

from __future__ import annotations

import re
from pathlib import Path

from questvector.config import STOPWORDS
from questvector.core.models import Capability, ChronologyEntry, Dossier, ImpactStatement
from questvector.exceptions import ParseError

_HEADING_RE = re.compile(r"^#{2}\s+(?P<heading>.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*[-*•]\s+(?P<text>.+?)\s*$")
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/_-]*")
_UNCATEGORIZED = "Uncategorized"
_MIN_TOKEN_LEN = 2


def tokenize(text: str) -> frozenset[str]:
    """Extract a normalized keyword set from free text.

    Args:
        text: Arbitrary natural-language text (a bullet, a job description,
            etc.).

    Returns:
        A frozenset of lowercased tokens with stopwords and single-character
        tokens removed. This is intentionally a simple, dependency-free
        heuristic (no stemming/lemmatization or POS tagging) — see
        :mod:`questvector.core.matcher` for how it is consumed and where its
        limitations are documented.
    """
    tokens = (match.group(0).lower() for match in _TOKEN_RE.finditer(text))
    return frozenset(
        token for token in tokens if len(token) >= _MIN_TOKEN_LEN and token not in STOPWORDS
    )


def _read_text(path: Path) -> str:
    """Read a Markdown file as UTF-8 text.

    Args:
        path: Path to the file to read.

    Returns:
        The file's decoded text content.

    Raises:
        ParseError: If the file does not exist, cannot be read, or is not
            valid UTF-8.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ParseError(
            f"Dossier file not found: {path.name}", context={"path": str(path)}
        ) from exc
    except UnicodeDecodeError as exc:
        raise ParseError(
            f"Dossier file is not valid UTF-8 text: {path.name}",
            context={"path": str(path)},
        ) from exc
    except OSError as exc:
        raise ParseError(
            f"Could not read dossier file: {path.name}", context={"path": str(path), "os_error": str(exc)}
        ) from exc
    return content


def _parse_sections(content: str, *, source_name: str) -> list[tuple[str, list[str]]]:
    """Split raw Markdown text into ``(heading, bullets)`` sections.

    Args:
        content: Raw file content.
        source_name: File name, used only for error context.

    Returns:
        A list of ``(heading, bullets)`` tuples in document order. Bullets
        preceding the first heading are grouped under ``"Uncategorized"``.

    Raises:
        ParseError: If the content is empty/whitespace-only, or contains no
            recognizable headings or bullets at all.
    """
    if not content.strip():
        raise ParseError(f"Dossier file is empty: {source_name}", context={"file": source_name})

    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_bullets: list[str] = []

    def _flush() -> None:
        if current_heading is not None:
            sections.append((current_heading, current_bullets.copy()))

    for line in content.splitlines():
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            _flush()
            current_heading = heading_match.group("heading")
            current_bullets = []
            continue

        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            if current_heading is None:
                current_heading = _UNCATEGORIZED
            current_bullets.append(bullet_match.group("text"))

    _flush()

    if not sections:
        raise ParseError(
            f"No headings or bullet items found in: {source_name}",
            context={"file": source_name},
        )
    return sections


def parse_capabilities(path: Path) -> tuple[Capability, ...]:
    """Parse a ``Capabilities.md`` file into :class:`Capability` entries.

    Each level-2 heading is treated as a capability domain, and each bullet
    beneath it becomes one :class:`Capability` in that domain.

    Args:
        path: Path to the Capabilities Markdown file.

    Returns:
        A tuple of parsed capabilities, in document order.

    Raises:
        ParseError: If the file is missing, unreadable, or contains no
            parsable headings/bullets.
    """
    content = _read_text(path)
    sections = _parse_sections(content, source_name=path.name)
    capabilities: list[Capability] = []
    for domain, bullets in sections:
        for bullet in bullets:
            capabilities.append(Capability(domain=domain, text=bullet, keywords=tokenize(bullet)))
    return tuple(capabilities)


def parse_chronology(path: Path) -> tuple[ChronologyEntry, ...]:
    """Parse a ``Chronology.md`` file into :class:`ChronologyEntry` entries.

    Each level-2 heading is treated as one role/timeframe entry, and its
    bullets are that role's responsibilities/achievements.

    Args:
        path: Path to the Chronology Markdown file.

    Returns:
        A tuple of parsed chronology entries, in document order.

    Raises:
        ParseError: If the file is missing, unreadable, or contains no
            parsable headings/bullets.
    """
    content = _read_text(path)
    sections = _parse_sections(content, source_name=path.name)
    entries: list[ChronologyEntry] = []
    for heading, bullets in sections:
        keywords: set[str] = set()
        for bullet in bullets:
            keywords |= tokenize(bullet)
        entries.append(
            ChronologyEntry(heading=heading, bullets=tuple(bullets), keywords=frozenset(keywords))
        )
    return tuple(entries)


def parse_impact(path: Path) -> tuple[ImpactStatement, ...]:
    """Parse an ``Impact.md`` file into :class:`ImpactStatement` entries.

    Each level-2 heading groups a set of quantified-impact bullets.

    Args:
        path: Path to the Impact Markdown file.

    Returns:
        A tuple of parsed impact statement groups, in document order.

    Raises:
        ParseError: If the file is missing, unreadable, or contains no
            parsable headings/bullets.
    """
    content = _read_text(path)
    sections = _parse_sections(content, source_name=path.name)
    statements: list[ImpactStatement] = []
    for heading, bullets in sections:
        keywords: set[str] = set()
        for bullet in bullets:
            keywords |= tokenize(bullet)
        statements.append(
            ImpactStatement(heading=heading, bullets=tuple(bullets), keywords=frozenset(keywords))
        )
    return tuple(statements)


def parse_dossier(workspace_dir: Path) -> Dossier:
    """Parse whichever canonical dossier files exist in a workspace.

    Per the Stage 1 blueprint decision, missing dossier files are tolerated
    (a dossier need not have all three documents to be scored) — only a
    *present but malformed* file raises.

    Args:
        workspace_dir: Directory expected to contain ``Capabilities.md``,
            ``Chronology.md``, and/or ``Impact.md``.

    Returns:
        A :class:`Dossier` built from whichever files were present. Missing
        files contribute empty tuples for their section.

    Raises:
        ParseError: If a present dossier file cannot be parsed.
    """
    from questvector.config import CAPABILITIES_FILENAME, CHRONOLOGY_FILENAME, IMPACT_FILENAME

    capabilities: tuple[Capability, ...] = ()
    chronology: tuple[ChronologyEntry, ...] = ()
    impact: tuple[ImpactStatement, ...] = ()

    capabilities_path = workspace_dir / CAPABILITIES_FILENAME
    if capabilities_path.exists():
        capabilities = parse_capabilities(capabilities_path)

    chronology_path = workspace_dir / CHRONOLOGY_FILENAME
    if chronology_path.exists():
        chronology = parse_chronology(chronology_path)

    impact_path = workspace_dir / IMPACT_FILENAME
    if impact_path.exists():
        impact = parse_impact(impact_path)

    return Dossier(capabilities=capabilities, chronology=chronology, impact=impact)
