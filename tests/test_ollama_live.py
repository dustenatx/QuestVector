"""Opt-in live test of narrative generation against a local Ollama server.

The live test is skipped unless ``QV_OLLAMA_LIVE=1`` is set, so the default
suite and CI never need a running server (see ``docs/DEVELOPMENT.md``).
Optional settings:

* ``QV_OLLAMA_MODEL``: model tag, already pulled (default:
  ``DEFAULT_OLLAMA_MODEL``, currently ``gemma4:12b-it-q4_K_M``).
* ``QV_OLLAMA_HOST``: server URL (default: ``http://localhost:11434``).
* ``QV_OLLAMA_TIMEOUT``: seconds to wait (default: the provider's default).

It uses only the synthetic dossier in ``tests/fixtures/ollama_live``. It
checks the plumbing (a non-empty answer, no error), not accuracy: the
fixture's ``answer_key.json`` is for scoring output by hand, and automatic
accuracy checks belong to backlog item 5.

The fixture checks below always run, so a broken fixture fails in CI.
"""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path

import pytest

from questvector.config import CAPABILITIES_FILENAME, CHRONOLOGY_FILENAME, IMPACT_FILENAME
from questvector.core import matcher
from questvector.core.llm import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    build_narrative_prompt,
    create_narrative_generator,
)
from questvector.core.markdown_parser import parse_dossier
from questvector.core.templates import load_template

FIXTURES = Path(__file__).parent / "fixtures" / "ollama_live"
DOSSIER_FILES = (CAPABILITIES_FILENAME, CHRONOLOGY_FILENAME, IMPACT_FILENAME)
# qv export --narrative sends this many capability bullets (questvector/cli.py).
CAPABILITIES_SENT = 20


def _answer_key() -> dict[str, object]:
    """Load the fixture's answer key."""
    return json.loads((FIXTURES / "answer_key.json").read_text(encoding="utf-8"))


def _trap_forms() -> dict[str, list[str]]:
    """Return each trap keyword's spellings, lowercased."""
    traps = _answer_key()["trap_keywords"]
    assert isinstance(traps, dict)
    return {name: [form.lower() for form in forms] for name, forms in traps.items()}


def _narrative_prompt() -> str:
    """Build the prompt exactly as ``qv export --narrative`` does."""
    dossier = parse_dossier(FIXTURES)
    jd_text = (FIXTURES / "job_description.txt").read_text(encoding="utf-8")
    job_description = matcher.parse_job_description(jd_text, source="job_description.txt")
    template_file = resources.files("questvector.data.starter_templates") / "devops-senior-mgr.qv-mission.yaml"
    with resources.as_file(template_file) as template_path:
        template = load_template(template_path)
    dossier_context = "\n".join(c.text for c in dossier.capabilities[:CAPABILITIES_SENT])
    return build_narrative_prompt(dossier_context, job_description.raw_text, tone_style=template.tone_style)


# --- Fixture checks (always run, no network) ---------------------------------


def test_fixture_dossier_reaches_the_model_whole() -> None:
    dossier = parse_dossier(FIXTURES)

    assert dossier.capabilities
    assert len(dossier.capabilities) <= CAPABILITIES_SENT


@pytest.mark.parametrize("filename", DOSSIER_FILES)
def test_fixture_trap_keywords_are_absent_from_the_dossier(filename: str) -> None:
    text = (FIXTURES / filename).read_text(encoding="utf-8").lower()

    for name, forms in _trap_forms().items():
        assert not any(form in text for form in forms), f"{name} appears in {filename}"


def test_fixture_trap_keywords_are_in_the_job_description() -> None:
    text = (FIXTURES / "job_description.txt").read_text(encoding="utf-8").lower()

    for name, forms in _trap_forms().items():
        assert any(form in text for form in forms), f"{name} missing from the job description"


def test_fixture_prompt_contains_dossier_and_job_description() -> None:
    prompt = _narrative_prompt()

    assert "Prometheus and Grafana" in prompt
    assert "HashiCorp Vault" in prompt


# --- Live test (opt-in) -------------------------------------------------------


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("QV_OLLAMA_LIVE") != "1",
    reason="live Ollama test; set QV_OLLAMA_LIVE=1 with a local server running",
)
def test_ollama_generates_narrative_from_synthetic_dossier() -> None:
    timeout = os.environ.get("QV_OLLAMA_TIMEOUT")
    generator = create_narrative_generator(
        "ollama",
        model=os.environ.get("QV_OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL,
        host=os.environ.get("QV_OLLAMA_HOST") or DEFAULT_OLLAMA_HOST,
        timeout=float(timeout) if timeout else None,
    )

    # An unreachable server or missing model raises LLMError and fails the
    # test: the user opted in, so a skip would hide the problem.
    narrative = generator.generate(_narrative_prompt())

    assert narrative.strip()
