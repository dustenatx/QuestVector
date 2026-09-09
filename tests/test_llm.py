"""Unit tests for questvector.core.llm.

External boundary (the Anthropic SDK / network) is always mocked here --
no test in this module makes a real network call.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from questvector.core.llm import AnthropicNarrativeGenerator, build_narrative_prompt
from questvector.exceptions import LLMError


def test_generator_requires_api_key() -> None:
    with pytest.raises(LLMError):
        AnthropicNarrativeGenerator(api_key="")


def test_generator_raises_when_anthropic_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "anthropic", None)  # forces ImportError on `import anthropic`
    with pytest.raises(LLMError):
        AnthropicNarrativeGenerator(api_key="sk-test")


def test_generate_returns_text_from_mocked_client() -> None:
    from anthropic.types import TextBlock

    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = SimpleNamespace(
            content=[TextBlock(type="text", text="Tailored summary paragraph.")]
        )

        generator = AnthropicNarrativeGenerator(api_key="sk-test")
        result = generator.generate("some prompt")

    assert result == "Tailored summary paragraph."
    mock_client.messages.create.assert_called_once()


def test_generate_raises_on_empty_response_content() -> None:
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = SimpleNamespace(content=[])

        generator = AnthropicNarrativeGenerator(api_key="sk-test")
        with pytest.raises(LLMError):
            generator.generate("some prompt")


def test_generate_raises_when_no_text_blocks_present() -> None:
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", text=None)]
        )

        generator = AnthropicNarrativeGenerator(api_key="sk-test")
        with pytest.raises(LLMError):
            generator.generate("some prompt")


def test_generate_wraps_api_error_as_llm_error() -> None:
    import anthropic

    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="boom", request=MagicMock(), body=None
        )

        generator = AnthropicNarrativeGenerator(api_key="sk-test")
        with pytest.raises(LLMError):
            generator.generate("some prompt")


def test_build_narrative_prompt_includes_both_inputs() -> None:
    prompt = build_narrative_prompt("Dossier facts here", "Job description here")
    assert "Dossier facts here" in prompt
    assert "Job description here" in prompt
