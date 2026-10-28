"""LLM narrative-generation integration -- multiple providers, one interface.

This is the one deliberate exception to this project's local-only
distribution policy (see ``README.md``): generating narrative text (e.g. a
tailored resume summary) from dossier + match data calls out to a
configured LLM provider. Distribution stays local -- nothing about this
feature is fetched, hosted, or installed from anywhere but the provider's
own API or, for the local option below, a server already running on the
user's machine -- but three of the four supported providers make an
outbound network call at *runtime*, and that is worth being explicit about.

Four providers are supported, chosen deliberately to cover both "bring your
own cloud key" and "stay fully local":

* ``anthropic`` -- Claude, via the Anthropic Messages API. Remote.
* ``openai`` -- OpenAI's models (the same company and API behind the
  ChatGPT product, though a ChatGPT Plus subscription is a *different*
  account/billing relationship from an OpenAI API key -- see
  :data:`PROVIDERS` and the setup link below). Remote.
* ``gemini`` -- Google's Gemini models, via the ``google-genai`` SDK. Remote.
* ``ollama`` -- a locally-installed and locally-running Ollama server
  (see https://ollama.com). No API key, no network call ever leaves the
  machine; this is the only one of the four that doesn't reintroduce a
  network dependency.

Every provider's narrative generation is off by default and only runs when
the user explicitly opts in: a cloud provider requires a key stored via
``qv vault set-key --provider <name>``, and every provider requires an
explicit user action to trigger (the desktop UI exposes this as a
"Generate Narrative" button rather than anything automatic). Callers
integrating this module should preserve that same explicitness rather than
calling it implicitly or on a background timer.

Each concrete generator is defined behind the small :class:`NarrativeGenerator`
protocol so the matching/export pipeline never depends on a concrete SDK --
this keeps every provider's SDK an *optional* dependency (``pip install
questvector[llm-anthropic]``, ``questvector[llm-openai]``,
``questvector[llm-gemini]``, or all three via ``questvector[llm]``; Ollama
needs no extra since it's driven over HTTP with the standard library) and
keeps the rest of the system fully testable with a mock generator and zero
network access, per this project's error-handling and testing standards.
Use :func:`create_narrative_generator` rather than instantiating a provider
class directly -- it is the single place that knows how to turn a provider
id + stored vault settings into a working generator, so callers (the CLI,
the desktop bridge) don't duplicate that dispatch logic.

**Adding a fifth provider (remote or local):** the registry is
data-driven, specifically so this doesn't require touching the CLI, the
vault, or the desktop bridge -- they all enumerate :data:`PROVIDERS`
rather than hardcoding provider names. Adding one is three steps, all in
this module:

1. Write a class implementing :class:`NarrativeGenerator` (one ``generate``
   method), following the pattern of the existing four -- raise
   :class:`LLMError` for a missing key, a missing SDK, an API failure, or
   an empty response.
2. Write a small factory function matching the
   ``(*, api_key, model, host, timeout) -> NarrativeGenerator`` shape (see
   ``_make_anthropic`` etc. below) that calls your class's constructor,
   ignoring whichever of ``api_key``/``host``/``timeout`` your provider
   doesn't need.
3. Add one :class:`ProviderSpec` entry to :data:`PROVIDERS` with that
   factory. That's it -- no other file needs to change.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from questvector.exceptions import LLMError

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_OLLAMA_MODEL = "gemma4:12b-it-q4_K_M"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
# Seconds to wait for a local Ollama response. Generous because a local
# model can be slow to load and run, and waiting costs nothing.
DEFAULT_OLLAMA_TIMEOUT = 300.0

# Backward-compatible alias -- earlier versions of this module supported
# only Anthropic, and named its default model plain ``DEFAULT_MODEL``.
DEFAULT_MODEL = DEFAULT_ANTHROPIC_MODEL

_NARRATIVE_SYSTEM_PROMPT = (
    "You are a career narrative assistant. Given a candidate's dossier "
    "excerpts and a target job description, write a concise, factual, "
    "first-person resume summary paragraph. Never invent employers, "
    "titles, metrics, or skills that are not present in the supplied "
    "dossier excerpts."
)


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Static metadata describing one supported LLM provider.

    Attributes:
        provider_id: Stable identifier used in the vault, the CLI's
            ``--provider`` flag, and the desktop bridge (e.g. ``"openai"``).
        display_name: Human-readable label for UI/CLI output. Spells out
            the OpenAI/ChatGPT relationship explicitly since that's a
            common point of confusion (see module docstring).
        is_local: ``True`` only for the Ollama provider -- the only one
            that never makes a network call off the local machine.
        requires_api_key: Whether :func:`create_narrative_generator` needs
            a non-empty ``api_key`` for this provider.
        default_model: Model id used when the caller doesn't override one.
        api_key_setup_url: Where a user gets an API key for this provider,
            or ``None`` for providers that don't need one (Ollama). Shown
            by the CLI and desktop UI at the moment a key is requested, so
            the user isn't left guessing where to go.
        setup_note: A short human-readable clarification shown alongside
            the setup link -- e.g. spelling out that an OpenAI API key is
            not the same thing as a ChatGPT Plus subscription.
        install_extra: The ``pip install`` extra that provides this
            provider's SDK, or ``None`` if no extra package is needed
            (Ollama is driven over plain HTTP via the standard library).
        factory: Builds a ready-to-use generator for this provider. Called
            as ``factory(api_key=..., model=..., host=..., timeout=...)``
            by :func:`create_narrative_generator` -- a provider that
            doesn't need one of these (e.g. Ollama ignores ``api_key``)
            simply ignores that argument.
    """

    provider_id: str
    display_name: str
    is_local: bool
    requires_api_key: bool
    default_model: str
    api_key_setup_url: str | None
    setup_note: str
    install_extra: str | None
    factory: Callable[..., "NarrativeGenerator"]


def _make_anthropic(
    *, api_key: str | None, model: str, host: str | None, timeout: float | None
) -> "NarrativeGenerator":
    return AnthropicNarrativeGenerator(api_key or "", model=model)


def _make_openai(
    *, api_key: str | None, model: str, host: str | None, timeout: float | None
) -> "NarrativeGenerator":
    return OpenAINarrativeGenerator(api_key or "", model=model)


def _make_gemini(
    *, api_key: str | None, model: str, host: str | None, timeout: float | None
) -> "NarrativeGenerator":
    return GeminiNarrativeGenerator(api_key or "", model=model)


def _make_ollama(
    *, api_key: str | None, model: str, host: str | None, timeout: float | None
) -> "NarrativeGenerator":
    return OllamaNarrativeGenerator(
        model=model,
        host=host or DEFAULT_OLLAMA_HOST,
        timeout=timeout if timeout is not None else DEFAULT_OLLAMA_TIMEOUT,
    )


PROVIDERS: dict[str, ProviderSpec] = {
    "anthropic": ProviderSpec(
        provider_id="anthropic",
        display_name="Anthropic (Claude)",
        is_local=False,
        requires_api_key=True,
        default_model=DEFAULT_ANTHROPIC_MODEL,
        api_key_setup_url="https://console.anthropic.com/settings/keys",
        setup_note="Create a key on the Anthropic Console; billing is separate from a claude.ai subscription.",
        install_extra="questvector[llm-anthropic]",
        factory=_make_anthropic,
    ),
    "openai": ProviderSpec(
        provider_id="openai",
        display_name="OpenAI (the API behind ChatGPT)",
        is_local=False,
        requires_api_key=True,
        default_model=DEFAULT_OPENAI_MODEL,
        api_key_setup_url="https://platform.openai.com/api-keys",
        setup_note=(
            "A ChatGPT Plus login is not the same account as an OpenAI API key -- "
            "keys are created (and billed separately) on the OpenAI Platform site, "
            "not inside the ChatGPT app."
        ),
        install_extra="questvector[llm-openai]",
        factory=_make_openai,
    ),
    "gemini": ProviderSpec(
        provider_id="gemini",
        display_name="Google Gemini",
        is_local=False,
        requires_api_key=True,
        default_model=DEFAULT_GEMINI_MODEL,
        api_key_setup_url="https://aistudio.google.com/apikey",
        setup_note="Create a free API key in Google AI Studio.",
        install_extra="questvector[llm-gemini]",
        factory=_make_gemini,
    ),
    "ollama": ProviderSpec(
        provider_id="ollama",
        display_name="Ollama (local, no cloud account)",
        is_local=True,
        requires_api_key=False,
        default_model=DEFAULT_OLLAMA_MODEL,
        api_key_setup_url="https://ollama.com/download",
        setup_note=(
            "No account or key needed -- install Ollama, run it locally, and "
            "`ollama pull <model>` the model you want before using it here."
        ),
        install_extra=None,
        factory=_make_ollama,
    ),
}


def _redact(text: str, secret: str) -> str:
    """Remove an API key from text that is about to reach the user.

    SDK error messages are copied into :class:`LLMError` messages, which
    the CLI prints and the desktop app displays; this keeps the key out of
    them even if an SDK ever echoes it.

    Args:
        text: The message text.
        secret: The API key to remove. An empty key leaves ``text`` as is.

    Returns:
        ``text`` with every occurrence of ``secret`` replaced by
        ``[redacted]``.
    """
    return text.replace(secret, "[redacted]") if secret else text


class NarrativeGenerator(Protocol):
    """Interface for anything that can turn a prompt into narrative text."""

    def generate(self, prompt: str) -> str:
        """Generate narrative text for the given prompt.

        Args:
            prompt: The fully-assembled prompt (dossier context + JD).

        Returns:
            The generated narrative text.

        Raises:
            LLMError: If generation fails for any reason.
        """
        ...


class AnthropicNarrativeGenerator:
    """:class:`NarrativeGenerator` backed by the Anthropic Messages API.

    Requires the optional ``anthropic`` dependency
    (``pip install questvector[llm-anthropic]``).
    """

    def __init__(
        self, api_key: str, *, model: str = DEFAULT_ANTHROPIC_MODEL, max_tokens: int = 600
    ) -> None:
        """Initialize the generator with credentials and model settings.

        Args:
            api_key: The Anthropic API key, read from the encrypted vault
                (see :mod:`questvector.core.vault`) -- never from a
                plaintext config file.
            model: The Claude model identifier to use.
            max_tokens: Maximum tokens to generate per call.

        Raises:
            LLMError: If ``api_key`` is empty, or the ``anthropic`` package
                is not installed.
        """
        if not api_key:
            raise LLMError("No Anthropic API key configured in the vault")
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError(
                "The 'anthropic' package is not installed; install with "
                "'pip install questvector[llm-anthropic]' to enable Anthropic narrative generation"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)
        self._api_key = api_key  # kept only to redact it from error messages
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        """Generate narrative text via the Anthropic Messages API.

        Args:
            prompt: The fully-assembled prompt (dossier context + JD).

        Returns:
            The generated narrative text, stripped of leading/trailing
            whitespace.

        Raises:
            LLMError: If the API call fails (network error, auth failure,
                rate limit, or an unexpected/empty response).
        """
        import anthropic
        from anthropic.types import TextBlock

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=_NARRATIVE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as exc:
            raise LLMError(
                f"LLM API call failed: {_redact(str(exc), self._api_key)}",
                context={"model": self._model},
            ) from exc

        if not response.content:
            raise LLMError("LLM returned an empty response", context={"model": self._model})

        text_blocks = [block.text for block in response.content if isinstance(block, TextBlock)]
        if not text_blocks:
            raise LLMError("LLM response contained no text content", context={"model": self._model})
        return "\n".join(text_blocks).strip()


class OpenAINarrativeGenerator:
    """:class:`NarrativeGenerator` backed by the OpenAI Chat Completions API.

    This talks to the OpenAI Platform API -- the same underlying models as
    the ChatGPT product, but a separate account and API key from a ChatGPT
    subscription (see :data:`PROVIDERS`\\ ``["openai"].setup_note``).

    Requires the optional ``openai`` dependency
    (``pip install questvector[llm-openai]``).
    """

    def __init__(
        self, api_key: str, *, model: str = DEFAULT_OPENAI_MODEL, max_tokens: int = 600
    ) -> None:
        """Initialize the generator with credentials and model settings.

        Args:
            api_key: The OpenAI API key, read from the encrypted vault.
            model: The OpenAI model identifier to use.
            max_tokens: Maximum tokens to generate per call.

        Raises:
            LLMError: If ``api_key`` is empty, or the ``openai`` package is
                not installed.
        """
        if not api_key:
            raise LLMError("No OpenAI API key configured in the vault")
        try:
            import openai
        except ImportError as exc:
            raise LLMError(
                "The 'openai' package is not installed; install with "
                "'pip install questvector[llm-openai]' to enable OpenAI narrative generation"
            ) from exc
        self._client = openai.OpenAI(api_key=api_key)
        self._api_key = api_key  # kept only to redact it from error messages
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        """Generate narrative text via the OpenAI Chat Completions API.

        Args:
            prompt: The fully-assembled prompt (dossier context + JD).

        Returns:
            The generated narrative text, stripped of leading/trailing
            whitespace.

        Raises:
            LLMError: If the API call fails (network error, auth failure,
                rate limit, or an unexpected/empty response).
        """
        import openai

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": _NARRATIVE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
        except openai.OpenAIError as exc:
            raise LLMError(
                f"LLM API call failed: {_redact(str(exc), self._api_key)}",
                context={"model": self._model},
            ) from exc

        choices = response.choices
        content = choices[0].message.content if choices else None
        if not content:
            raise LLMError("LLM returned an empty response", context={"model": self._model})
        return content.strip()


class GeminiNarrativeGenerator:
    """:class:`NarrativeGenerator` backed by Google's Gemini API.

    Requires the optional ``google-genai`` dependency
    (``pip install questvector[llm-gemini]``).
    """

    def __init__(
        self, api_key: str, *, model: str = DEFAULT_GEMINI_MODEL, max_tokens: int = 600
    ) -> None:
        """Initialize the generator with credentials and model settings.

        Args:
            api_key: The Gemini API key, read from the encrypted vault.
            model: The Gemini model identifier to use.
            max_tokens: Maximum output tokens per call.

        Raises:
            LLMError: If ``api_key`` is empty, or the ``google-genai``
                package is not installed.
        """
        if not api_key:
            raise LLMError("No Gemini API key configured in the vault")
        try:
            from google import genai
        except ImportError as exc:
            raise LLMError(
                "The 'google-genai' package is not installed; install with "
                "'pip install questvector[llm-gemini]' to enable Gemini narrative generation"
            ) from exc
        self._client = genai.Client(api_key=api_key)
        self._api_key = api_key  # kept only to redact it from error messages
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        """Generate narrative text via the Gemini API.

        Args:
            prompt: The fully-assembled prompt (dossier context + JD).

        Returns:
            The generated narrative text, stripped of leading/trailing
            whitespace.

        Raises:
            LLMError: If the API call fails (network error, auth failure,
                rate limit, or an unexpected/empty response).
        """
        from google.genai import errors as genai_errors
        from google.genai import types as genai_types

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=_NARRATIVE_SYSTEM_PROMPT,
                    max_output_tokens=self._max_tokens,
                ),
            )
        except genai_errors.APIError as exc:
            raise LLMError(
                f"LLM API call failed: {_redact(str(exc), self._api_key)}",
                context={"model": self._model},
            ) from exc

        text = getattr(response, "text", None)
        if not text:
            raise LLMError("LLM returned an empty response", context={"model": self._model})
        return text.strip()


class OllamaNarrativeGenerator:
    """:class:`NarrativeGenerator` backed by a locally-running Ollama server.

    This is the only generator in this module that makes no request off
    the local machine: it talks over plain HTTP (standard library only, no
    extra dependency) to an Ollama server the user has already installed
    and started, with the target model already pulled. If nothing is
    listening at ``host``, the model isn't pulled, or the server is too
    slow, generation fails with a clear, actionable :class:`LLMError`
    rather than a raw traceback.

    Thinking is always switched off (``"think": false``): a thinking model
    otherwise spends the whole token budget reasoning and returns no
    answer. See ``docs/decisions/0012-ollama-thinking-off.md``.
    """

    def __init__(
        self,
        *,
        model: str,
        host: str = DEFAULT_OLLAMA_HOST,
        max_tokens: int = 600,
        timeout: float = DEFAULT_OLLAMA_TIMEOUT,
    ) -> None:
        """Initialize the generator with a model name and server address.

        Args:
            model: The Ollama model tag to use (e.g. ``"gemma4:12b-it-q4_K_M"``). Must
                already be pulled locally via ``ollama pull <model>``.
            host: Base URL of the local Ollama server.
            max_tokens: Maximum tokens to generate per call.
            timeout: Seconds to wait for the server's full response.

        Raises:
            LLMError: If ``model`` is empty, ``host`` isn't an
                ``http://`` or ``https://`` URL, or ``timeout`` isn't
                positive.
        """
        if not model:
            raise LLMError(
                "An Ollama model name is required (e.g. 'gemma4:12b-it-q4_K_M') -- "
                "run 'ollama pull <model>' first"
            )
        # urllib also opens file:// and ftp:// URLs; only HTTP reaches Ollama.
        parsed = urllib.parse.urlsplit(host)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise LLMError(
                f"The Ollama host must be an http:// or https:// URL, got {host!r} "
                f"(the default is {DEFAULT_OLLAMA_HOST})",
                context={"host": host},
            )
        if timeout <= 0:
            raise LLMError(
                f"The Ollama timeout must be a positive number of seconds, got {timeout!r}",
                context={"timeout": timeout},
            )
        self._model = model
        self._host = host.rstrip("/")
        self._max_tokens = max_tokens
        self._timeout = timeout

    def generate(self, prompt: str) -> str:
        """Generate narrative text via the local Ollama HTTP API.

        Args:
            prompt: The fully-assembled prompt (dossier context + JD).

        Returns:
            The generated narrative text, stripped of leading/trailing
            whitespace.

        Raises:
            LLMError: If the local Ollama server can't be reached, doesn't
                have the model, rejects the request, doesn't answer within
                the timeout, or returns an empty or unparseable response.
        """
        payload = json.dumps(
            {
                "model": self._model,
                "prompt": f"{_NARRATIVE_SYSTEM_PROMPT}\n\n{prompt}",
                "stream": False,
                "think": False,
                "options": {"num_predict": self._max_tokens},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self._host}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        context: dict[str, object] = {"model": self._model, "host": self._host}
        try:
            # The scheme is limited to http(s) in __init__.
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                body = json.loads(resp.read().decode("utf-8"))
        # HTTPError subclasses URLError, so it must be caught first: a 404
        # means the server answered, not that it's unreachable.
        except urllib.error.HTTPError as exc:
            detail = _ollama_error_detail(exc)
            context["ollama_error"] = detail
            if exc.code == 404:
                raise LLMError(
                    f"Model '{self._model}' isn't downloaded on the Ollama server at "
                    f"{self._host} -- run 'ollama pull {self._model}'",
                    context=context,
                ) from exc
            raise LLMError(f"Ollama rejected the request (HTTP {exc.code}): {detail}", context=context) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise self._timeout_error(context) from exc
            raise LLMError(
                f"Could not reach the local Ollama server at {self._host} -- "
                "is it running? (see https://ollama.com)",
                context=context,
            ) from exc
        # A timeout while reading the response isn't wrapped in URLError.
        except TimeoutError as exc:
            raise self._timeout_error(context) from exc
        except json.JSONDecodeError as exc:
            raise LLMError("Ollama returned a response that could not be parsed", context=context) from exc

        text = body.get("response")
        if not text:
            context["done_reason"] = body.get("done_reason")
            context["eval_count"] = body.get("eval_count")
            if body.get("done_reason") != "length":
                raise LLMError("Ollama returned an empty response", context=context)
            if body.get("thinking"):
                raise LLMError(
                    f"The model spent its whole {self._max_tokens}-token limit reasoning "
                    "and never answered -- it is a thinking model that ignored the "
                    "request to switch thinking off",
                    context=context,
                )
            raise LLMError(
                f"The model hit its {self._max_tokens}-token limit before writing an answer",
                context=context,
            )
        return text.strip()

    def _timeout_error(self, context: dict[str, object]) -> LLMError:
        """Build the error for a server that didn't answer in time.

        Args:
            context: Diagnostic details for the error.

        Returns:
            An :class:`LLMError` naming the timeout and how to raise it.
        """
        return LLMError(
            f"Ollama didn't finish within its {self._timeout:g}-second limit -- the model may be "
            "loading or too slow for this machine; raise the limit with "
            "'qv vault set-key --provider ollama --timeout SECONDS'",
            context={**context, "timeout": self._timeout},
        )


def _ollama_error_detail(exc: urllib.error.HTTPError) -> str:
    """Extract Ollama's error message from an HTTP error response.

    Args:
        exc: The HTTP error raised by ``urlopen``.

    Returns:
        The ``error`` field of Ollama's JSON body, or the HTTP reason
        phrase if the body is missing or isn't Ollama's JSON shape.
    """
    try:
        detail = json.loads(exc.read().decode("utf-8")).get("error")
    except (OSError, ValueError, AttributeError):
        detail = None
    return str(detail) if detail else str(exc.reason)


def create_narrative_generator(
    provider: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    host: str | None = None,
    timeout: float | None = None,
) -> NarrativeGenerator:
    """Build a :class:`NarrativeGenerator` for the given provider id.

    This is the single dispatch point from a provider id (as stored in the
    vault, or passed on the CLI) to a concrete generator -- callers (the
    CLI, the desktop bridge) should use this instead of importing and
    instantiating a provider class directly, so provider selection logic
    lives in one place.

    Args:
        provider: One of the keys in :data:`PROVIDERS`
            (``"anthropic"``, ``"openai"``, ``"gemini"``, ``"ollama"``).
        api_key: The provider's API key. Required for every provider
            except ``"ollama"``, which needs none.
        model: Model override. Defaults to the provider's
            :attr:`ProviderSpec.default_model` when not given.
        host: Server override, used only by ``"ollama"`` to point at a
            non-default local server address.
        timeout: Seconds to wait for a response, used only by
            ``"ollama"``. Defaults to :data:`DEFAULT_OLLAMA_TIMEOUT`.

    Returns:
        A ready-to-use :class:`NarrativeGenerator`.

    Raises:
        LLMError: If ``provider`` is not a known provider id, or a
            provider that requires an API key was not given one.
    """
    spec = PROVIDERS.get(provider)
    if spec is None:
        known = ", ".join(sorted(PROVIDERS))
        raise LLMError(f"Unknown LLM provider '{provider}' (known providers: {known})")

    resolved_model = model or spec.default_model
    return spec.factory(api_key=api_key, model=resolved_model, host=host, timeout=timeout)


def build_narrative_prompt(
    dossier_context: str, job_description: str, *, tone_style: str | None = None
) -> str:
    """Assemble the user-turn prompt for narrative generation.

    Args:
        dossier_context: Relevant excerpts pulled from the candidate's
            dossier (kept short and factual -- never the whole document).
        job_description: The target job description's raw text.
        tone_style: Optional tone hint from a mission template's
            ``output_formatting.tone_style`` (e.g. "executive-tactical"),
            per the ``CONTRIBUTING_TEMPLATES.md`` schema. When set, it is
            passed through as a stylistic instruction; it never overrides
            the factual-accuracy constraint in the system prompt.

    Returns:
        A single string ready to pass to :meth:`NarrativeGenerator.generate`.
    """
    tone_instruction = f"Write in a {tone_style} tone. " if tone_style else ""
    return (
        "Dossier excerpts:\n"
        f"{dossier_context.strip()}\n\n"
        "Target job description:\n"
        f"{job_description.strip()}\n\n"
        f"{tone_instruction}Write a 3-4 sentence resume summary tailored to "
        "this job, using only facts present in the dossier excerpts above."
    )
