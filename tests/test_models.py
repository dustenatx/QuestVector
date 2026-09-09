"""Unit tests for questvector.core.models."""

from __future__ import annotations

from questvector.core.models import (
    Capability,
    ChronologyEntry,
    Dossier,
    ImpactStatement,
    MissionTemplate,
    TemplateCategory,
)


def test_dossier_all_keywords_unions_all_sections() -> None:
    dossier = Dossier(
        capabilities=(Capability(domain="Cloud", text="aws", keywords=frozenset({"aws"})),),
        chronology=(ChronologyEntry(heading="Role", bullets=("x",), keywords=frozenset({"kubernetes"})),),
        impact=(ImpactStatement(heading="Impact", bullets=("y",), keywords=frozenset({"budget"})),),
    )
    assert dossier.all_keywords() == frozenset({"aws", "kubernetes", "budget"})


def test_dossier_all_keywords_empty_when_no_sections() -> None:
    assert Dossier().all_keywords() == frozenset()


def test_mission_template_weight_sum() -> None:
    template = MissionTemplate(
        template_id="t1",
        title="Test",
        categories=(
            TemplateCategory(name="a", weight=0.6),
            TemplateCategory(name="b", weight=0.4),
        ),
    )
    assert template.weight_sum() == 1.0


def test_mission_template_weight_sum_empty_categories() -> None:
    template = MissionTemplate(template_id="t1", title="Test", categories=())
    assert template.weight_sum() == 0.0
