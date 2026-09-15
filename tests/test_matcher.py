"""Unit tests for questvector.core.matcher."""

from __future__ import annotations

import pytest

from questvector.core.markdown_parser import tokenize
from questvector.core.matcher import parse_job_description, run_match
from questvector.core.models import AlertLevel, Capability, Dossier, MissionTemplate, TemplateCategory
from questvector.exceptions import MatchEngineError


def _template(*categories: TemplateCategory, **kwargs: object) -> MissionTemplate:
    return MissionTemplate(template_id="t1", title="Test Template", categories=categories, **kwargs)  # type: ignore[arg-type]


def test_parse_job_description_extracts_keywords() -> None:
    jd = parse_job_description("Senior AWS Kubernetes Engineer", source="test")
    assert "aws" in jd.keywords
    assert jd.source == "test"


def test_parse_job_description_empty_text_raises() -> None:
    with pytest.raises(MatchEngineError):
        parse_job_description("   ", source="test")


def test_run_match_full_coverage_yields_high_score() -> None:
    dossier = Dossier(
        capabilities=(Capability(domain="Cloud", text="aws terraform", keywords=tokenize("aws terraform")),)
    )
    jd = parse_job_description("Looking for AWS and Terraform experience", source="test")
    template = _template(TemplateCategory(name="cloud", weight=1.0, keywords=("aws", "terraform")))

    result = run_match(dossier, jd, template)

    assert result.g_force_score == 100.0
    assert result.gaps == ()
    assert result.red_flags == ()
    assert result.alert_level == AlertLevel.SUCCESS


def test_run_match_zero_coverage_on_heavy_category_is_red_flag() -> None:
    dossier = Dossier(capabilities=(Capability(domain="Other", text="unrelated skills", keywords=tokenize("unrelated skills")),))
    jd = parse_job_description("Requires deep Kubernetes and Terraform expertise", source="test")
    template = _template(TemplateCategory(name="cloud", weight=0.9, keywords=("kubernetes", "terraform")))

    result = run_match(dossier, jd, template)

    assert result.g_force_score < 40.0
    assert len(result.red_flags) == 1
    assert result.alert_level == AlertLevel.CRITICAL


def test_run_match_category_with_no_relevant_keywords_scores_as_fully_covered() -> None:
    dossier = Dossier()
    jd = parse_job_description("A job description with no overlapping terms at all", source="test")
    # Category keywords that don't appear in the JD at all -> nothing "relevant" to check.
    template = _template(TemplateCategory(name="niche", weight=1.0, keywords=("cobol", "mainframe")))

    result = run_match(dossier, jd, template)

    assert result.g_force_score == 100.0


def test_run_match_no_categories_raises() -> None:
    dossier = Dossier()
    jd = parse_job_description("Some text", source="test")
    template = _template()
    with pytest.raises(MatchEngineError):
        run_match(dossier, jd, template)


def test_run_match_normalizes_weights_not_summing_to_one() -> None:
    dossier = Dossier(capabilities=(Capability(domain="Cloud", text="aws", keywords=tokenize("aws")),))
    jd = parse_job_description("Needs AWS experience", source="test")
    # Weights sum to 2.0, not 1.0 -- score should still normalize to 100%.
    template = _template(TemplateCategory(name="cloud", weight=2.0, keywords=("aws",)))

    result = run_match(dossier, jd, template)

    assert result.g_force_score == 100.0


def test_run_match_partial_coverage_produces_gaps() -> None:
    dossier = Dossier(capabilities=(Capability(domain="Cloud", text="aws", keywords=tokenize("aws")),))
    jd = parse_job_description("Needs AWS and Kubernetes experience", source="test")
    template = _template(TemplateCategory(name="cloud", weight=1.0, keywords=("aws", "kubernetes")))

    result = run_match(dossier, jd, template)

    assert 0.0 < result.g_force_score < 100.0
    assert "kubernetes" in result.gaps


def test_run_match_red_flag_phrase_found_in_jd_text() -> None:
    dossier = Dossier(capabilities=(Capability(domain="Cloud", text="aws", keywords=tokenize("aws")),))
    jd = parse_job_description(
        "Needs AWS experience. Note: candidate must wear many hats.", source="test"
    )
    template = _template(
        TemplateCategory(name="cloud", weight=1.0, keywords=("aws",)),
        red_flag_phrases=("wear many hats",),
    )

    result = run_match(dossier, jd, template)

    assert any("wear many hats" in flag for flag in result.red_flags)


def test_run_match_red_flag_phrase_absent_from_jd_text_no_flag() -> None:
    dossier = Dossier(capabilities=(Capability(domain="Cloud", text="aws", keywords=tokenize("aws")),))
    jd = parse_job_description("Needs AWS experience, standard schedule.", source="test")
    template = _template(
        TemplateCategory(name="cloud", weight=1.0, keywords=("aws",)),
        red_flag_phrases=("wear many hats",),
    )

    result = run_match(dossier, jd, template)

    assert result.red_flags == ()


def test_run_match_red_flag_phrase_is_case_insensitive() -> None:
    dossier = Dossier(capabilities=(Capability(domain="Cloud", text="aws", keywords=tokenize("aws")),))
    jd = parse_job_description("Needs AWS experience. Must WEAR MANY HATS daily.", source="test")
    template = _template(
        TemplateCategory(name="cloud", weight=1.0, keywords=("aws",)),
        red_flag_phrases=("wear many hats",),
    )

    result = run_match(dossier, jd, template)

    assert len(result.red_flags) == 1


def test_run_match_weak_categories_below_threshold() -> None:
    dossier = Dossier(capabilities=(Capability(domain="Cloud", text="aws", keywords=tokenize("aws")),))
    jd = parse_job_description("Needs AWS Terraform Kubernetes Docker experience", source="test")
    template = _template(
        TemplateCategory(name="cloud", weight=1.0, keywords=("aws", "terraform", "kubernetes", "docker")),
        gap_coverage_threshold=0.5,
    )

    result = run_match(dossier, jd, template)

    # Only 1 of 4 keywords covered (25%), below the 0.5 threshold.
    assert "cloud" in result.weak_categories


def test_run_match_no_weak_categories_when_threshold_not_set() -> None:
    dossier = Dossier()
    jd = parse_job_description("Needs AWS Terraform experience", source="test")
    template = _template(TemplateCategory(name="cloud", weight=1.0, keywords=("aws", "terraform")))

    result = run_match(dossier, jd, template)

    assert result.weak_categories == ()


def test_run_match_weak_category_triggers_warning_alert_even_without_gaps_or_red_flags() -> None:
    # High overall score (single fully-relevant keyword covered) but the
    # template still flags this category as weak via a strict threshold.
    dossier = Dossier(capabilities=(Capability(domain="Cloud", text="aws", keywords=tokenize("aws")),))
    jd = parse_job_description("Needs AWS experience", source="test")
    template = _template(
        TemplateCategory(name="cloud", weight=1.0, keywords=("aws",)),
        gap_coverage_threshold=1.5,  # impossible threshold -> always "weak"
    )

    result = run_match(dossier, jd, template)

    assert result.weak_categories == ("cloud",)
    assert result.alert_level == AlertLevel.WARNING
