"""Unit tests for questvector.core.llm.

External boundary (each provider's SDK / network, and the local Ollama
HTTP server) is always mocked here -- no test in this module makes a real
network call or requires a running Ollama server.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from questvector.core.llm import (
    PROVIDERS,
    AnthropicNarrativeGenerator,
    GeminiNarrativeGenerator,
    OllamaNarrativeGenerator,
    OpenAINarrativeGenerator,
    ProviderSpec,
    build_narrative_prompt,
    create_narrative_generator,
)
from questvector.exceptions import LLMError

# --- Anthropic -------------------------------------------------------------


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


# --- OpenAI ------------------------------------------------------------


def test_openai_generator_requires_api_key() -> None:
    with pytest.raises(LLMError):
        OpenAINarrativeGenerator(api_key="")


def test_openai_generator_raises_when_openai_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "openai", None)
    with pytest.raises(LLMError):
        OpenAINarrativeGenerator(api_key="sk-test")


def test_openai_generate_returns_text_from_mocked_client() -> None:
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Tailored summary paragraph."))]
        )

        generator = OpenAINarrativeGenerator(api_key="sk-test")
        result = generator.generate("some prompt")

    assert result == "Tailored summary paragraph."
    mock_client.chat.completions.create.assert_called_once()


def test_openai_generate_raises_on_empty_choices() -> None:
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = SimpleNamespace(choices=[])

        generator = OpenAINarrativeGenerator(api_key="sk-test")
        with pytest.raises(LLMError):
            generator.generate("some prompt")


def test_openai_generate_wraps_api_error_as_llm_error() -> None:
    import openai

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = openai.APIError(
            message="boom", request=MagicMock(), body=None
        )

        generator = OpenAINarrativeGenerator(api_key="sk-test")
        with pytest.raises(LLMError):
            generator.generate("some prompt")


# --- Gemini --------------------------------------------------------------


def test_gemini_generator_requires_api_key() -> None:
    with pytest.raises(LLMError):
        GeminiNarrativeGenerator(api_key="")


def test_gemini_generator_raises_when_sdk_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "google.genai", None)
    with pytest.raises(LLMError):
        GeminiNarrativeGenerator(api_key="sk-test")


def test_gemini_generate_returns_text_from_mocked_client() -> None:
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = SimpleNamespace(text="Tailored summary paragraph.")

        generator = GeminiNarrativeGenerator(api_key="sk-test")
        result = generator.generate("some prompt")

    assert result == "Tailored summary paragraph."
    mock_client.models.generate_content.assert_called_once()


def test_gemini_generate_raises_on_empty_text() -> None:
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = SimpleNamespace(text=None)

        generator = GeminiNarrativeGenerator(api_key="sk-test")
        with pytest.raises(LLMError):
            generator.generate("some prompt")


def test_gemini_generate_wraps_api_error_as_llm_error() -> None:
    from google.genai import errors as genai_errors

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = genai_errors.APIError(
            500, {"error": {"message": "boom"}}
        )

        generator = GeminiNarrativeGenerator(api_key="sk-test")
        with pytest.raises(LLMError):
            generator.generate("some prompt")


# --- Ollama (local) --------------------------------------------------------


def test_ollama_generator_requires_model_name() -> None:
    with pytest.raises(LLMError):
        OllamaNarrativeGenerator(model="")


def test_ollama_generate_returns_text_from_mocked_server() -> None:
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps({"response": "Tailored summary paragraph."}).encode("utf-8")
    fake_response.__enter__.return_value = fake_response

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
        generator = OllamaNarrativeGenerator(model="llama3.1")
        result = generator.generate("some prompt")

    assert result == "Tailored summary paragraph."
    mock_urlopen.assert_called_once()


def test_ollama_generate_raises_when_server_unreachable() -> None:
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
        generator = OllamaNarrativeGenerator(model="llama3.1")
        with pytest.raises(LLMError):
            generator.generate("some prompt")


def test_ollama_generate_raises_on_empty_response_field() -> None:
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps({"response": ""}).encode("utf-8")
    fake_response.__enter__.return_value = fake_response

    with patch("urllib.request.urlopen", return_value=fake_response):
        generator = OllamaNarrativeGenerator(model="llama3.1")
        with pytest.raises(LLMError):
            generator.generate("some prompt")


# --- Provider registry / factory --------------------------------------------


def test_providers_registry_has_all_four_providers() -> None:
    assert set(PROVIDERS) == {"anthropic", "openai", "gemini", "ollama"}


def test_only_ollama_is_marked_local() -> None:
    assert PROVIDERS["ollama"].is_local is True
    assert all(not spec.is_local for name, spec in PROVIDERS.items() if name != "ollama")


def test_only_ollama_does_not_require_api_key() -> None:
    assert PROVIDERS["ollama"].requires_api_key is False
    assert all(spec.requires_api_key for name, spec in PROVIDERS.items() if name != "ollama")


def test_create_narrative_generator_unknown_provider_raises() -> None:
    with pytest.raises(LLMError):
        create_narrative_generator("not-a-real-provider", api_key="sk-test")


def test_create_narrative_generator_dispatches_to_anthropic() -> None:
    generator = create_narrative_generator("anthropic", api_key="sk-test")
    assert isinstance(generator, AnthropicNarrativeGenerator)


def test_create_narrative_generator_dispatches_to_openai() -> None:
    generator = create_narrative_generator("openai", api_key="sk-test")
    assert isinstance(generator, OpenAINarrativeGenerator)


def test_create_narrative_generator_dispatches_to_gemini() -> None:
    generator = create_narrative_generator("gemini", api_key="sk-test")
    assert isinstance(generator, GeminiNarrativeGenerator)


def test_create_narrative_generator_dispatches_to_ollama_without_api_key() -> None:
    generator = create_narrative_generator("ollama", model="llama3.1")
    assert isinstance(generator, OllamaNarrativeGenerator)


def test_registering_a_fifth_provider_requires_no_change_to_the_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    # Proves the registry is genuinely data-driven: a new ProviderSpec with
    # its own factory is enough to make create_narrative_generator() (and,
    # by extension, the CLI's --provider choices and the desktop bridge's
    # list_llm_providers()) support it -- no branch anywhere needs editing.
    class _FakeGenerator:
        def __init__(self, greeting: str) -> None:
            self.greeting = greeting

        def generate(self, prompt: str) -> str:
            return f"{self.greeting}: {prompt}"

    def _make_fake(*, api_key: object, model: str, host: object) -> _FakeGenerator:
        return _FakeGenerator(greeting=model)

    fake_spec = ProviderSpec(
        provider_id="fake-local",
        display_name="Fake Local Provider",
        is_local=True,
        requires_api_key=False,
        default_model="fake-model",
        api_key_setup_url=None,
        setup_note="A test-only provider.",
        install_extra=None,
        factory=_make_fake,
    )
    monkeypatch.setitem(PROVIDERS, "fake-local", fake_spec)

    generator = create_narrative_generator("fake-local")

    assert isinstance(generator, _FakeGenerator)
    assert generator.generate("hi") == "fake-model: hi"


# --- Prompt assembly ---------------------------------------------------------


def test_build_narrative_prompt_includes_both_inputs() -> None:
    prompt = build_narrative_prompt("Dossier facts here", "Job description here")
    assert "Dossier facts here" in prompt
    assert "Job description here" in prompt


def test_build_narrative_prompt_includes_tone_style_when_given() -> None:
    prompt = build_narrative_prompt("Dossier facts", "JD text", tone_style="executive-tactical")
    assert "executive-tactical" in prompt
