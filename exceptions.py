"""Custom exception hierarchy for QuestVector.

All application-raised errors derive from :class:`QuestVectorError` so callers
(CLI, desktop bridge, tests) can catch broadly at a boundary while still being
able to catch narrowly where they need specific handling. Never catch these
with a bare ``except:`` — catch :class:`QuestVectorError` or a specific
subclass.
"""

from __future__ import annotations


class QuestVectorError(Exception):
    """Base class for all application-raised errors in QuestVector.

    Args:
        message: Human-readable description of the failure.
        context: Optional mapping of extra diagnostic details (file paths,
            offending values, etc.) that callers may want to log or display.
    """

    def __init__(self, message: str, *, context: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, object] = context or {}

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.context:
            details = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message} ({details})"
        return self.message


class ParseError(QuestVectorError):
    """Raised when a Markdown dossier document cannot be parsed.

    Covers malformed structure, unreadable encoding, or content that does not
    match the expected QuestVector dossier schema.
    """


class ValidationError(QuestVectorError):
    """Raised when a mission template or other structured input fails schema
    or business-rule validation (e.g., category weights that do not sum to
    1.00 and ``--fix`` was not requested).
    """


class VaultError(QuestVectorError):
    """Raised when the encrypted local vault cannot be read, written, or
    decrypted (wrong passphrase, corrupted ciphertext, missing vault file).
    """


class WorkspaceError(QuestVectorError):
    """Raised for local workspace/filesystem problems: initializing a
    workspace over an existing non-empty directory, permission failures, or
    a concurrent-write conflict detected via the workspace lock file.
    """


class ExportError(QuestVectorError):
    """Raised when compiling a resume/dossier bundle into PDF or DOCX fails,
    or when an unsupported export format is requested.
    """


class MatchEngineError(QuestVectorError):
    """Raised when the micro-diff matching engine cannot score a job
    description against a dossier (e.g., empty/unreadable JD input).
    """


class LLMError(QuestVectorError):
    """Raised when a call to a configured LLM narrative-generation backend
    fails: missing API key, network failure, or an unexpected response
    shape. Callers should degrade gracefully (e.g., skip narrative
    generation) rather than crash the whole workflow.
    """
