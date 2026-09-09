"""LLM narrative-generation integration.

Per the Stage 1 blueprint decision, this build includes real LLM
integration for turning dossier + match data into narrative text (e.g. a
tailored resume summary), rather than keeping the tool a strictly offline
air-gapped system as MASTER_DEVELOPER_SPEC.pdf's "Zero-Cloud" branding
claims. This is a deliberate scope decision, not an oversight: enabling
this feature means QuestVector makes outbound network calls to the
configured LLM provider whenever narrative generation is invoked, which is
not "air-gapped." Callers should surface that clearly to the end user
(the desktop UI does, via an explicit "Generate Narrative" action rather
than an automatic background call).

The integration is defined behind a small :class:`NarrativeGenerator`
protocol so the matching/export pipeline never depends on a concrete SDK —
this keeps ``anthropic`` an optional dependency (``pip install
questvector[llm]``) and keeps the rest of the system fully testable with a
mock generator and zero network access, per this project's error-handling
and testing standards.
"""

from __future__ import annotations

from typing import Protocol

from questvector.exceptions import LLMError

DEFAULT_MODEL = "claude-sonnet-4-5"

_NARRATIVE_SYSTEM_PROMPT = (
    "You are a career narrative assistant. Given a candidate's dossier "
    "excerpts and a target job description, write a concise, factual, "
    "first-person resume summary paragraph. Never invent employers, "
    "titles, metrics, or skills that are not present in the supplied "
    "dossier excerpts."
)


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
    (``pip install questvector[llm]``).
    """

    def __init__(self, api_key: str, *, model: str = DEFAULT_MODEL, max_tokens: int = 600) -> None:
        """Initialize the generator with credentials and model settings.

        Args:
            api_key: The Anthropic API key, read from the encrypted vault
                (see :mod:`questvector.core.vault`) — never from a
                plaintext config file.
            model: The Claude model identifier to use.
            max_tokens: Maximum tokens to generate per call.

        Raises:
            LLMError: If ``api_key`` is empty, or the ``anthropic`` package
                is not installed.
        """
        if not api_key:
            raise LLMError("No LLM API key configured in the vault")
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError(
                "The 'anthropic' package is not installed; install with "
                "'pip install questvector[llm]' to enable narrative generation"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)
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
            raise LLMError(f"LLM API call failed: {exc}", context={"model": self._model}) from exc

        if not response.content:
            raise LLMError("LLM returned an empty response", context={"model": self._model})

        text_blocks = [block.text for block in response.content if isinstance(block, TextBlock)]
        if not text_blocks:
            raise LLMError("LLM response contained no text content", context={"model": self._model})
        return "\n".join(text_blocks).strip()


def build_narrative_prompt(dossier_context: str, job_description: str) -> str:
    """Assemble the user-turn prompt for narrative generation.

    Args:
        dossier_context: Relevant excerpts pulled from the candidate's
            dossier (kept short and factual — never the whole document).
        job_description: The target job description's raw text.

    Returns:
        A single string ready to pass to :meth:`NarrativeGenerator.generate`.
    """
    return (
        "Dossier excerpts:\n"
        f"{dossier_context.strip()}\n\n"
        "Target job description:\n"
        f"{job_description.strip()}\n\n"
        "Write a 3-4 sentence resume summary tailored to this job, using "
        "only facts present in the dossier excerpts above."
    )
